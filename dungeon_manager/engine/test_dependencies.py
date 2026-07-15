import ast
import sys
from pathlib import Path


def test_engine_package_has_only_standard_library_and_internal_dependencies():
    package_root = Path(__file__).resolve().parent
    forbidden_internal_packages = {
        "ai",
        "foundry",
        "managers",
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
