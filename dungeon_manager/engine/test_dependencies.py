import ast
import sys
from pathlib import Path


def test_engine_package_has_only_standard_library_and_internal_dependencies():
    package_root = Path(__file__).resolve().parent
    forbidden_internal_packages = {
        "ai",
        "foundry",
        "managers",
        "rules",
        "storage",
        "tools",
    }

    for path in sorted(package_root.glob("*.py")):
        if path.name.startswith("test_"):
            continue

        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                imported_modules = [node.module or ""]
            else:
                continue

            for module in imported_modules:
                top_level = module.split(".", 1)[0]
                assert top_level in sys.stdlib_module_names
                assert not (
                    module.startswith("dungeon_manager.")
                    and module.split(".")[1] in forbidden_internal_packages
                )


def test_campaign_runtime_is_a_provider_and_sql_free_composition_boundary():
    path = Path(__file__).resolve().parent.parent / "campaign_runtime.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imported_modules = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    absolute_from_modules = {
        node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.level == 0
    }
    source = path.read_text(encoding="utf-8")

    assert "sqlite3" not in imported_modules
    assert not any(
        module.startswith("dungeon_manager." + forbidden)
        for module in absolute_from_modules
        for forbidden in ("ai", "foundry", "rules", "tools")
    )
    assert "SELECT " not in source
    assert "INSERT INTO " not in source


def test_automation_policy_has_no_dispatcher_or_external_engine_dependency():
    path = Path(__file__).resolve().parent / "automation.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    relative_imports = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.level > 0
    }

    assert relative_imports == {"_json", "command"}


def test_dice_foundation_has_only_immutable_json_and_standard_library_dependencies():
    path = Path(__file__).resolve().parent / "dice.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    relative_imports = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.level > 0
    }
    absolute_imports = {
        alias.name.split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }

    assert relative_imports == {"_json"}
    assert absolute_imports <= sys.stdlib_module_names


def test_combat_domain_has_only_dice_and_immutable_json_engine_dependencies():
    path = Path(__file__).resolve().parent / "combat_domain.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    relative_imports = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.level > 0
    }
    absolute_imports = {
        alias.name.split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }

    assert relative_imports == {"_json", "dice"}
    assert absolute_imports <= sys.stdlib_module_names


def test_controlled_round_adjudication_has_only_engine_data_dependencies():
    path = Path(__file__).resolve().parent / "controlled_round.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    relative_imports = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.level > 0
    }
    absolute_imports = {
        alias.name.split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }

    assert relative_imports == {"_json", "combat_domain", "dice", "game_event"}
    assert absolute_imports <= sys.stdlib_module_names


def test_verified_narration_packet_has_only_authoritative_engine_data_dependencies():
    path = Path(__file__).resolve().parent / "verified_narration.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    relative_imports = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.level > 0
    }
    absolute_imports = {
        alias.name.split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }

    assert relative_imports == {
        "_json",
        "controlled_round",
        "dice",
        "journals",
        "world_state",
    }
    assert absolute_imports <= sys.stdlib_module_names


def test_narration_provider_and_boundary_have_no_tools_or_concrete_ai_dependency():
    package_root = Path(__file__).resolve().parent.parent
    paths = (
        package_root / "ai" / "narration_provider.py",
        package_root / "verified_narration.py",
    )
    forbidden_modules = {
        "dungeon_manager.ai.ollama_provider",
        "dungeon_manager.ai.provider",
        "dungeon_manager.ai.tool_agent",
        "dungeon_manager.ai.tool_call_parser",
        "dungeon_manager.ai.tool_executor",
        "dungeon_manager.tools",
    }

    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imports = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        } | {
            node.module or ""
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.level == 0
        }
        assert not (imports & forbidden_modules)
        assert "sqlite3" not in imports


def test_policy_gated_dispatcher_uses_only_existing_engine_boundaries():
    path = Path(__file__).resolve().parent / "policy_gated_dispatcher.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    relative_imports = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.level > 0
    }
    accessed_attributes = {
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
    }

    assert relative_imports == {
        "_json",
        "automation",
        "command",
        "game_engine",
        "result",
    }
    assert "_handlers" not in accessed_attributes
    assert "handler" not in accessed_attributes


def test_event_and_audit_foundations_have_only_data_boundary_dependencies():
    package_root = Path(__file__).resolve().parent
    expected_relative_imports = {
        "_time.py": set(),
        "game_event.py": {"_json", "_time", "command"},
        "audit.py": {"_json", "_time", "command"},
        "journals.py": {"_json", "audit", "game_event"},
    }

    for filename, expected in expected_relative_imports.items():
        path = package_root / filename
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        relative_imports = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.level > 0
        }

        assert relative_imports == expected


def test_durable_event_journal_store_depends_only_on_event_data_boundaries():
    package_root = Path(__file__).resolve().parent
    path = package_root / "event_journal_store.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    relative_imports = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.level > 0
    }
    accessed_names = {
        node.id for node in ast.walk(tree) if isinstance(node, ast.Name)
    }

    assert relative_imports == {
        "_json",
        "durable_journal",
        "game_event",
        "journals",
    }
    assert "AuditedCommandPipeline" not in accessed_names
    assert "GameEventJournal" not in accessed_names


def test_event_producing_result_uses_only_existing_engine_data_boundaries():
    package_root = Path(__file__).resolve().parent
    expected_relative_imports = {
        "result.py": {"_json", "game_event"},
        "game_engine.py": {"_json", "command", "result"},
    }

    for filename, expected in expected_relative_imports.items():
        path = package_root / filename
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        relative_imports = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.level > 0
        }
        accessed_names = {
            node.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Name)
        }

        assert relative_imports == expected
        assert "GameEventJournal" not in accessed_names
        assert "CommandAuditJournal" not in accessed_names


def test_audited_pipeline_uses_only_existing_engine_and_audit_boundaries():
    path = Path(__file__).resolve().parent / "audited_pipeline.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    relative_imports = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.level > 0
    }
    accessed_attributes = {
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
    }

    assert relative_imports == {
        "_json",
        "_time",
        "audit",
        "automation",
        "command",
        "durable_journal",
        "journals",
        "policy_gated_dispatcher",
        "world_state",
        "world_state_holder",
        "world_state_recovery",
    }
    assert "_handlers" not in accessed_attributes
    assert "handler" not in accessed_attributes


def test_durable_capability_has_only_typed_event_data_dependencies():
    path = Path(__file__).resolve().parent / "durable_journal.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    relative_imports = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.level > 0
    }
    imported_modules = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }

    assert relative_imports == {"_json", "journals"}
    assert "sqlite3" not in imported_modules


def test_startup_hydration_uses_no_sqlite_ai_or_dispatch_boundaries():
    path = Path(__file__).resolve().parent / "startup_hydration.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    relative_imports = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.level > 0
    }
    imported_modules = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    accessed_names = {
        node.id for node in ast.walk(tree) if isinstance(node, ast.Name)
    }

    assert relative_imports == {
        "_json",
        "durable_journal",
        "event_journal_store",
        "journals",
        "world_state",
        "world_state_holder",
    }
    assert "sqlite3" not in imported_modules
    for forbidden in (
        "AutomationPolicy",
        "CommandAuditJournal",
        "Foundry",
        "GameEngine",
        "HumanApprovalDecision",
        "PolicyGatedCommandDispatcher",
    ):
        assert forbidden not in accessed_names


def test_sqlite_and_sql_remain_confined_to_event_journal_store():
    package_root = Path(__file__).resolve().parent
    for path in sorted(package_root.glob("*.py")):
        if path.name.startswith("test_"):
            continue
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        imported_modules = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        if path.name == "event_journal_store.py":
            assert "sqlite3" in imported_modules
            continue
        assert "sqlite3" not in imported_modules
        assert "SELECT " not in source
        assert "INSERT INTO " not in source
        assert "UPDATE " not in source
        assert "DELETE FROM " not in source


def test_world_state_projection_uses_only_event_data_boundaries():
    package_root = Path(__file__).resolve().parent
    projection_path = package_root / "world_state.py"
    projection_tree = ast.parse(
        projection_path.read_text(encoding="utf-8"),
        filename=str(projection_path),
    )
    relative_imports = {
        node.module
        for node in ast.walk(projection_tree)
        if isinstance(node, ast.ImportFrom) and node.level > 0
    }

    assert relative_imports == {"_json", "game_event", "journals"}

    for filename in ("journals.py",):
        path = package_root / filename
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imported_boundaries = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.level > 0
        }
        accessed_names = {
            node.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Name)
        }

        assert "world_state" not in imported_boundaries
        assert "WorldStateProjector" not in accessed_names


def test_world_state_holder_depends_only_on_projection_boundary():
    path = Path(__file__).resolve().parent / "world_state_holder.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    relative_imports = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.level > 0
    }
    accessed_names = {
        node.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Name)
    }

    assert relative_imports == {"world_state"}
    assert "GameEventJournal" not in accessed_names
    assert "AuditedCommandPipeline" not in accessed_names


def test_world_state_recovery_result_depends_only_on_safe_data_boundaries():
    path = Path(__file__).resolve().parent / "world_state_recovery.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    relative_imports = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.level > 0
    }
    accessed_names = {
        node.id for node in ast.walk(tree) if isinstance(node, ast.Name)
    }

    assert relative_imports == {"_json", "world_state"}
    assert "GameEngine" not in accessed_names
    assert "GameEventJournal" not in accessed_names
    assert "CommandAuditJournal" not in accessed_names
    assert "PolicyGatedCommandDispatcher" not in accessed_names


def test_client_neutral_contract_and_application_layers_point_inward_only():
    package_root = Path(__file__).resolve().parent.parent
    application_root = package_root / "application"
    expected_relative_imports = {
        "contracts.py": set(),
        "ports.py": {"contracts"},
        "controlled_fixture.py": {"contracts", "ports"},
    }
    forbidden_names = {
        "CampaignRuntime",
        "ControlledRoundRuntime",
        "EventJournalStore",
        "Foundry",
        "JSONStorage",
        "NarrationProvider",
        "ToolAgent",
        "ToolExecutor",
        "ToolRegistry",
    }

    for filename, expected in expected_relative_imports.items():
        path = application_root / filename
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        relative_imports = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.level > 0
        }
        absolute_modules = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        } | {
            node.module or ""
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.level == 0
        }
        accessed_names = {
            node.id for node in ast.walk(tree) if isinstance(node, ast.Name)
        }

        assert relative_imports == expected
        assert all(
            module.split(".", 1)[0] in sys.stdlib_module_names
            for module in absolute_modules
        )
        assert not (accessed_names & forbidden_names)
        assert "Integrate AI" not in source


def test_in_process_controlled_fixture_adapter_has_no_edge_client_or_ai_tools():
    path = (
        Path(__file__).resolve().parent.parent
        / "adapters"
        / "in_process_controlled_fixture.py"
    )
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    absolute_modules = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.level == 0
    }
    forbidden_prefixes = (
        "dungeon_manager.ai",
        "dungeon_manager.foundry",
        "dungeon_manager.managers",
        "dungeon_manager.storage",
        "dungeon_manager.tools",
        "dungeon_manager.ui",
    )

    assert not any(
        module.startswith(forbidden_prefixes) for module in absolute_modules
    )
    assert "sqlite3" not in absolute_modules
    assert "Integrate AI" not in source


def test_authoritative_engine_never_imports_application_or_adapter_layers():
    package_root = Path(__file__).resolve().parent

    for path in sorted(package_root.glob("*.py")):
        if path.name.startswith("test_"):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        absolute_modules = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        } | {
            node.module or ""
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.level == 0
        }
        assert not any(
            module.startswith(
                (
                    "dungeon_manager.application",
                    "dungeon_manager.adapters",
                )
            )
            for module in absolute_modules
        )
