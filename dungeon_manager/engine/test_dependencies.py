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
