import json

from dungeon_manager.ai.provider import AIProvider

from . import live_tool_loop_validation as live_validation


class StubProvider(AIProvider):
    def __init__(self, responses):
        self.responses = list(responses)
        self.prompts = []

    def generate(self, prompt):
        self.prompts.append(prompt)
        if not self.responses:
            raise AssertionError("unexpected provider call")
        return self.responses.pop(0)


def test_live_validation_requires_explicit_environment_opt_in(
    monkeypatch,
    capsys,
):
    monkeypatch.delenv(
        live_validation.OPT_IN_ENVIRONMENT_VARIABLE,
        raising=False,
    )

    def forbidden_config_load():
        raise AssertionError("config must not load without live opt-in")

    monkeypatch.setattr(
        live_validation,
        "load_config",
        forbidden_config_load,
    )

    assert live_validation.main() == 2
    report = json.loads(capsys.readouterr().err)
    assert report["all_scenarios_passed"] is False
    assert live_validation.OPT_IN_ENVIRONMENT_VARIABLE in report["error"]


def test_required_scenarios_use_real_components_with_exact_call_limits(tmp_path):
    character_name = "Talvorn TEST123456"
    missing_name = "Neverborn TEST123456"
    provider = StubProvider(
        [
            "A clear daytime sky is blue.",
            json.dumps(
                {
                    "tool": "create_character",
                    "arguments": {
                        "name": character_name,
                        "race": "Human",
                        "character_class": "Fighter",
                    },
                }
            ),
            f"{character_name} is ready.",
            json.dumps(
                {
                    "tool": "load_character",
                    "arguments": {"name": character_name},
                }
            ),
            f"Loaded {character_name}.",
            json.dumps(
                {
                    "tool": "load_character",
                    "arguments": {"name": missing_name},
                }
            ),
            f"The character {missing_name} was not found.",
        ]
    )

    report = live_validation.run_scenarios(
        provider,
        tmp_path,
        character_name,
        missing_name,
    )

    assert report["all_scenarios_passed"] is True
    assert [scenario["passed"] for scenario in report["scenarios"]] == [
        True,
        True,
        True,
        True,
    ]
    assert report["totals"] == {
        "provider_call_count": 7,
        "executor_invocation_count": 3,
        "registry_invocation_count": 3,
        "underlying_tool_invocation_count": 3,
        "underlying_tool_invocations_by_name": {
            "create_character": 1,
            "load_character": 2,
        },
    }
    assert len(provider.prompts) == 7
    assert provider.responses == []
    assert [
        scenario["provider_call_count"]
        for scenario in report["scenarios"]
    ] == [1, 2, 2, 2]
    assert [
        scenario["executor_invocation_count"]
        for scenario in report["scenarios"]
    ] == [0, 1, 1, 1]

    stored_path = (
        tmp_path / "characters" / f"{character_name.lower()}.json"
    )
    assert stored_path.is_file()
    assert json.loads(stored_path.read_text(encoding="utf-8")) == {
        "name": character_name,
        "race": "Human",
        "character_class": "Fighter",
        "level": 1,
        "description": "",
        "inventory": [],
        "notes": [],
    }
