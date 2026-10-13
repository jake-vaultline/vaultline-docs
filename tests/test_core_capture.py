import importlib.util
import inspect
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from vaultline_docs import capture as capture_module
from vaultline_docs.source import Source, load_guides


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("core_capture_harness", ROOT / "scripts/core_capture_harness.py")
HARNESS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HARNESS)


class CoreCaptureHarnessTests(unittest.TestCase):
    class Response:
        ok = True

        def __init__(self, value):
            self.value = value

        def json(self):
            return self.value

    class Page:
        def __init__(self, responses, live=True):
            self.responses = responses
            self.request = self
            self.live = live

        def get(self, url):
            return CoreCaptureHarnessTests.Response(self.responses[url.rsplit('/', 1)[-1]])

        def evaluate(self, _script):
            return self.live

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
                plan = HARNESS.plan(core, HARNESS.EXPECTED_CORE_REVISION, recipes, manifest, runtime,
                                    check_effective=False)
            self.assertEqual(plan["guide_ids"], ["search-collection"])
            self.assertEqual(plan["port"], 0)
            self.assertEqual(plan["headless_jobs"], 1)
            self.assertEqual(plan["root_growth_plan_bytes"], 2 * 1024 * 1024 * 1024)
            self.assertEqual(plan["process_plan"], 32)
            self.assertEqual(plan["capture_contract"], {"kind": "media-nexus-core", "version": 1})
            self.assertEqual(plan["capture_session"]["path"], "/__vaultline_docs/session")
            self.assertEqual(plan["capture_session"]["method"], "GET")
            self.assertEqual(plan["capture_proof"]["asset_id"], HARNESS.ASSET_ID)

    def test_shared_digest_matches_capture_contract(self):
        from vaultline_docs.source import digest
        manifest = json.loads((ROOT / "examples/deployments/core-1.0.158-docs.json").read_text())
        self.assertEqual(HARNESS.digest(manifest["config"]), digest(manifest["config"]))

    def test_live_core_proof_refuses_static_demo_mode(self):
        page = self.Page({"me": {"authenticated": True},
                          "v2": {"assets": [{"id": HARNESS.ASSET_ID}]}}, live=False)
        with self.assertRaisesRegex(ValueError, "static demo fallback refused"):
            capture_module.live_core_evidence(page, "http://127.0.0.1:1234")

    def test_generic_fixture_mode_performs_no_core_live_checks(self):
        identity = {"synthetic": True, "test_account": "docs-reviewer"}
        proof = capture_module.core_capture_proof(identity)
        self.assertIsNone(proof)
        page = self.Page({})
        self.assertEqual(capture_module.capture_step_evidence(
            page, "http://127.0.0.1:1234", proof, 1, "Fixture result"), {})

    def test_declared_core_requires_exact_proof_contract(self):
        identity = {"capture_contract": {"kind": "media-nexus-core", "version": 1},
                    "capture_session": capture_module.CORE_CAPTURE_SESSION}
        with self.assertRaisesRegex(ValueError, "requires the exact persistence proof"):
            capture_module.core_capture_proof(identity)
        identity["capture_proof"] = {"method": "GET", "path": "/wrong"}
        with self.assertRaisesRegex(ValueError, "requires the exact persistence proof"):
            capture_module.core_capture_proof(identity)

    def test_proof_cannot_fall_back_to_generic_capture(self):
        with self.assertRaisesRegex(ValueError, "requires a declared Core capture contract"):
            capture_module.core_capture_proof({"capture_proof": {}})
        with self.assertRaisesRegex(ValueError, "Unsupported Core capture contract"):
            capture_module.core_capture_proof({"capture_contract": {
                "kind": "media-nexus-core", "version": 2}})

    def test_core_step_evidence_refuses_live_proof_failure(self):
        page = self.Page({"me": {"authenticated": True},
                          "v2": {"assets": [{"id": HARNESS.ASSET_ID}]}}, live=False)
        with self.assertRaisesRegex(ValueError, "static demo fallback refused"):
            capture_module.capture_step_evidence(
                page, "http://127.0.0.1:1234", {"path": "/__vaultline_docs/proof"},
                1, "Live Core")

    def test_python_runtime_fence_is_set_before_core_imports(self):
        with tempfile.TemporaryDirectory() as temp, \
             mock.patch.object(HARNESS.sys, "dont_write_bytecode", False), \
             mock.patch.object(HARNESS.sys, "pycache_prefix", None):
            state = HARNESS.configure_python_runtime(Path(temp))
            self.assertTrue(HARNESS.sys.dont_write_bytecode)
            self.assertEqual(HARNESS.sys.pycache_prefix, str(Path(temp) / "cache"))
            self.assertEqual(state, {"dont_write_bytecode": True,
                                     "pycache_prefix": str(Path(temp) / "cache")})
        source = inspect.getsource(HARNESS.serve)
        self.assertLess(source.index("configure_python_runtime(root)"),
                        source.index('sys.path.insert(0, identity["core_root"])'))
        self.assertLess(source.index("configure_python_runtime(root)"),
                        source.index("import vaultline_config as core_config"))

    def test_persistence_proof_requires_member_and_unchanged_source(self):
        contract = {"path": "/__vaultline_docs/proof", "after_step": 2,
                    "collection": HARNESS.COLLECTION_NAME, "asset_id": HARNESS.ASSET_ID,
                    "source_path_sha256": HARNESS.digest(HARNESS.ASSET_SOURCE_PATH.encode())}
        proof = {"ui_mode": "live-core", "collection": {
            "name": HARNESS.COLLECTION_NAME, "note": HARNESS.COLLECTION_NOTE,
            "member_ids": [HARNESS.ASSET_ID], "member_count": 1},
            "asset": {"id": HARNESS.ASSET_ID,
                      "source_path_sha256": contract["source_path_sha256"],
                      "source_path_unchanged": True}}
        page = self.Page({"proof": proof})
        self.assertEqual(capture_module.persistence_evidence(
            page, "http://127.0.0.1:1234", contract, 3), proof)
        proof["collection"]["member_ids"] = []
        with self.assertRaisesRegex(ValueError, "exact synthetic member"):
            capture_module.persistence_evidence(page, "http://127.0.0.1:1234", contract, 3)

    def test_closed_environment_drops_hostile_deployment_provider_and_secret_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            inherited = {
                "PATH": "/usr/bin:/bin",
                "VAULTLINE_ACCESS_URL_STATE": "/client/access.json",
                "VAULTLINE_ARCHIVE_SITE_OVERLAY_PATH": "/client/site.json",
                "VAULTLINE_DEPLOYMENT_CONFIG_PATH": "/client/deployment.json",
                "VAULTLINE_SIGNED_RUNTIME_CONFIG_PATH": "/client/signed.json",
                "VAULTLINE_SECRETS_PATH": "/client/secrets.env",
                "VAULTLINE_R2_SECRET_ACCESS_KEY": "must-not-be-read-or-copied",
                "OPENAI_API_KEY": "must-not-be-read-or-copied",
            }
            env = HARNESS.runtime_environment(root, root / "runtime.json", inherited)
            self.assertEqual(env["HOME"], str(root / "home"))
            self.assertEqual(env["VAULTLINE_CONFIG_PATH"], str(root / "runtime.json"))
            for name in inherited:
                if name != "PATH":
                    self.assertNotIn(name, env)

    def test_pinned_core_accepts_config_and_matches_effective_manifest_identity(self):
        core = Path(os.environ.get(
            "VAULTLINE_DOCS_CORE_ROOT",
            "/Users/jakehalperin/Developer/Vaultline/worktrees/core/vlp-2189-docs-capture-source",
        ))
        if not core.is_dir():
            self.skipTest("exact pinned Core source view unavailable")
        self.assertEqual(HARNESS.git(core, "rev-parse", "HEAD"), HARNESS.EXPECTED_CORE_REVISION)
        self.assertEqual(HARNESS.git(core, "status", "--porcelain"), "")
        manifest = json.loads((ROOT / "examples/deployments/core-1.0.158-docs.json").read_text())
        with tempfile.TemporaryDirectory() as temp:
            private = Path(temp)
            for name in ("database", "derivatives", "home", "tmp", "cache"):
                (private / name).mkdir()
            config_path = private / "runtime.json"
            HARNESS.write_private(config_path, HARNESS.runtime_config(private))
            effective = HARNESS.load_effective_config(core, private, config_path, {
                "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                "VAULTLINE_ACCESS_URL_STATE": "/forbidden/access.json",
                "VAULTLINE_ARCHIVE_SITE_OVERLAY_PATH": "/forbidden/site.json",
                "VAULTLINE_DEPLOYMENT_CONFIG_PATH": "/forbidden/deployment.json",
                "VAULTLINE_SIGNED_RUNTIME_CONFIG_PATH": "/forbidden/signed.json",
                "VAULTLINE_R2_SECRET_ACCESS_KEY": "forbidden",
            })
            projected = HARNESS.validate_effective_identity(effective, manifest)
        self.assertEqual(projected, manifest["config"])
        self.assertNotIn("canonicalOrigin", projected)

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
