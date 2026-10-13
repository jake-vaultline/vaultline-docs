import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "portal_qualifier", ROOT / "scripts/qualify_core_guide_portal.py")
QUALIFIER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(QUALIFIER)


def packet(version="1.0.158", modules=None, organization="org_a", system="sys_a"):
    return {"organizationId": organization, "systemId": system,
            "deployment": {"version": version, "modules": modules or ["core", "archive"]}}


class FixtureTransport:
    def __init__(self, system=None):
        self.organization = {"id": "org_a", "name": "Synthetic Studio"}
        self.system = system or {"id": "sys_a", "organization_id": "org_a",
                                 "name": "Synthetic Studio", "version": "fixture-1.0.0",
                                 "modules_json": ["archive", "relay"]}
        self.calls = []

    def __call__(self, origin, method, path, body=None):
        self.calls.append((origin, method, path, body))
        if "organizations" in path:
            return [dict(self.organization)]
        if method == "PATCH":
            self.system.update(body)
        return [dict(self.system)]


class RecordingLocator:
    def __init__(self):
        self.calls = []

    def locator(self, selector):
        self.calls.append(("locator", selector))
        return self

    def get_by_text(self, value, exact=False):
        self.calls.append(("get_by_text", value, exact))
        return self


class PortalQualifierFixtureTests(unittest.TestCase):
    def test_exact_packet_seeds_only_expected_synthetic_system_and_reads_back(self):
        transport = FixtureTransport()
        profile = QUALIFIER.configure_fixture_system(
            "http://127.0.0.1:54321", packet(), transport=transport)
        self.assertEqual(profile, {"version": "1.0.158", "modules_json": ["core", "archive"]})
        self.assertEqual([call[1] for call in transport.calls], ["GET", "GET", "PATCH", "GET"])
        self.assertTrue(all("org_b" not in call[2] and "sys_b" not in call[2] for call in transport.calls))
        self.assertEqual(transport.system["version"], "1.0.158")
        self.assertEqual(transport.system["modules_json"], ["core", "archive"])

    def test_wrong_target_or_foreign_module_profile_is_refused_before_transport(self):
        for value in (packet(organization="org_b"), packet(system="sys_b"),
                      packet(modules=["archive", "relay"])):
            transport = FixtureTransport()
            with self.assertRaises(RuntimeError):
                QUALIFIER.configure_fixture_system("http://127.0.0.1:54321", value, transport=transport)
            self.assertEqual(transport.calls, [])

    def test_wrong_package_profile_is_refused(self):
        accepted = {"version": "1.0.158", "modules": ["core", "archive"]}
        for deployment in ({"version": "1.0.157", "modules": ["core", "archive"]},
                           {"version": "1.0.158", "modules": ["archive", "relay"]}):
            with self.assertRaisesRegex(RuntimeError, "differs from the accepted deployment"):
                QUALIFIER.verify_deployment_profile(deployment, accepted)

    def test_unexpected_fixture_identity_is_refused_without_patch(self):
        transport = FixtureTransport(system={"id": "sys_a", "organization_id": "org_b",
            "name": "Foreign System", "version": "fixture-1.0.0", "modules_json": ["archive"]})
        with self.assertRaisesRegex(RuntimeError, "expected synthetic sys_a"):
            QUALIFIER.configure_fixture_system("http://127.0.0.1:54321", packet(), transport=transport)
        self.assertNotIn("PATCH", [call[1] for call in transport.calls])

    def test_nonloopback_origin_is_refused(self):
        transport = FixtureTransport()
        with self.assertRaisesRegex(RuntimeError, "127.0.0.1"):
            QUALIFIER.configure_fixture_system(
                "http://portal.example.test:54321", packet(), transport=transport)
        self.assertEqual(transport.calls, [])

    def test_source_revision_targets_exact_metadata_code_when_release_notes_repeat_sha(self):
        revision = "98a373276de75fcf9510dfb02ffb89778b8ea324"
        release_notes = f"# Draft release notes\n\nSource revision: `{revision}`"
        self.assertIn(revision, release_notes)
        docs = RecordingLocator()
        result = QUALIFIER.source_revision_metadata(docs, revision)
        self.assertIs(result, docs)
        self.assertEqual(docs.calls, [
            ("locator", ".support-docs-footer details code"),
            ("get_by_text", revision, True),
        ])


if __name__ == "__main__":
    unittest.main()
