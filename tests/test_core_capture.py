import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from vaultline_docs.source import Source, load_guides


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("core_capture_harness", ROOT / "scripts/core_capture_harness.py")
HARNESS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HARNESS)


class CoreCaptureHarnessTests(unittest.TestCase):
    def test_inline_guide_binding_covers_runtime_actions(self):
        import subprocess
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp)
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            (repo / "app.py").write_text("Search media\n")
            subprocess.run(["git", "-C", str(repo), "add", "app.py"], check=True)
            subprocess.run(["git", "-C", str(repo), "-c", "user.name=Docs Test", "-c",
                            "user.email=docs@example.invalid", "commit", "-qm", "fixture"], check=True)
            recipe = {"guides": [{"id": "search", "title": "Search", "summary": "Search",
                "prerequisites": ["Ready"], "expected": ["Found"], "dependencies": [],
                "steps": [{"title": "Search", "instruction": "Search", "expected": "Found",
                           "actions": [{"op": "press", "selector": "input", "key": "Enter"}],
                           "assertions": [{"selector": "body", "text": "Found"}]}],
                "evidence": [{"path": "app.py", "anchor": "Search media"}]}]}
            _, blocked, first = load_guides(Source(repo), recipe)
            self.assertEqual(blocked, [])
            recipe["guides"][0]["steps"][0]["actions"][0]["key"] = "Tab"
            _, _, second = load_guides(Source(repo), recipe)
            self.assertNotEqual(first["search"], second["search"])

    def test_plan_is_one_exact_core_guide_and_private_runtime(self):
        with tempfile.TemporaryDirectory(dir=Path.home()) as temp:
            core = Path(temp) / "core"
            (core / "product").mkdir(parents=True)
            (core / "product/product.json").write_text(json.dumps({"coreVersion": "1.0.158"}))
            recipes = ROOT / "examples/media-nexus-core-1.0.158-recipes.json"
            manifest = ROOT / "examples/deployments/core-1.0.158-docs.json"
            runtime = Path(temp) / "runtime"
            bindings = {"search-collection": [{"path": "vaultline_app.jsx", "anchor": "Search media"}]}
            with mock.patch.object(HARNESS, "git", side_effect=[HARNESS.EXPECTED_CORE_REVISION, ""]), \
                 mock.patch("vaultline_docs.source.Source"), \
                 mock.patch("vaultline_docs.source.load_guides", return_value=([{"id": "search-collection"}], [], bindings)):
                plan = HARNESS.plan(core, HARNESS.EXPECTED_CORE_REVISION, recipes, manifest, runtime)
            self.assertEqual(plan["guide_ids"], ["search-collection"])
            self.assertEqual(plan["port"], 0)
            self.assertEqual(plan["headless_jobs"], 1)
            self.assertEqual(plan["root_growth_plan_bytes"], 2 * 1024 * 1024 * 1024)
            self.assertEqual(plan["process_plan"], 32)
            self.assertEqual(plan["capture_session"]["path"], "/__vaultline_docs/session")
            self.assertEqual(plan["capture_session"]["method"], "GET")

    def test_rejects_dirty_or_wrong_core(self):
        with tempfile.TemporaryDirectory(dir=Path.home()) as temp:
            core = Path(temp) / "core"
            (core / "product").mkdir(parents=True)
            (core / "product/product.json").write_text(json.dumps({"coreVersion": "1.0.158"}))
            args = (core, HARNESS.EXPECTED_CORE_REVISION,
                    ROOT / "examples/media-nexus-core-1.0.158-recipes.json",
                    ROOT / "examples/deployments/core-1.0.158-docs.json", Path(temp) / "runtime")
            with mock.patch.object(HARNESS, "git", side_effect=[HARNESS.EXPECTED_CORE_REVISION, "M foreign"]):
                with self.assertRaisesRegex(HARNESS.HarnessError, "clean"):
                    HARNESS.validate_inputs(*args)


if __name__ == "__main__":
    unittest.main()
