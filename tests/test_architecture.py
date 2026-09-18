import ast
import unittest
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1] / "password_manager"


def imported_modules(path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)
    return modules


class ArchitectureBoundaryTests(unittest.TestCase):
    def test_models_have_no_outward_package_dependencies(self):
        for path in (PACKAGE_ROOT / "models").glob("*.py"):
            with self.subTest(path=path.name):
                imports = imported_modules(path)
                self.assertFalse(
                    [module for module in imports if module.startswith("password_manager.")]
                )

    def test_services_do_not_import_views_or_data(self):
        forbidden = ("password_manager.views", "password_manager.data", "tkinter")
        for path in (PACKAGE_ROOT / "services").glob("*.py"):
            with self.subTest(path=path.name):
                imports = imported_modules(path)
                self.assertFalse(
                    [module for module in imports if module.startswith(forbidden)]
                )

    def test_views_do_not_import_data_implementations(self):
        for path in (PACKAGE_ROOT / "views").glob("*.py"):
            with self.subTest(path=path.name):
                imports = imported_modules(path)
                self.assertFalse(
                    [
                        module
                        for module in imports
                        if module.startswith("password_manager.data")
                    ]
                )


if __name__ == "__main__":
    unittest.main()
