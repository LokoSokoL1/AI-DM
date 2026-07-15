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


def test_automation_policy_has_no_dispatcher_or_external_engine_dependency():
    path = Path(__file__).resolve().parent / "automation.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    relative_imports = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.level > 0
    }

    assert relative_imports == {"_json", "command"}


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
        "journals",
        "policy_gated_dispatcher",
    }
    assert "_handlers" not in accessed_attributes
    assert "handler" not in accessed_attributes
