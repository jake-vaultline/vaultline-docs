#!/usr/bin/env python3
"""Qualify one captured Core guide in the existing local synthetic Portal flow.

This reviewed runtime harness never targets a hosted Portal. It accepts the exact Docs package and
Portal packet produced after real Core capture, verifies their hashes and identity, then uses the
Portal's existing mock Supabase fixture, administrator review UI, client UI and private downloads.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import time
import urllib.parse
import urllib.request
import zipfile

from playwright.sync_api import expect, sync_playwright


PINNED_PORTAL_REVISION = "ce77a0ce867e5229d9fdef9f94179cc048c2d3d3"
GUIDE_ID = "search-collection"
GUIDE_TITLE = "Search the archive and create a collection"
OVERRIDE_MARKER = "ARCHIVE-DOCS-"
PORTAL_FIXTURE_ORGANIZATION = "org_a"
PORTAL_FIXTURE_SYSTEM = "sys_a"
PORTAL_FIXTURE_NAME = "Synthetic Studio"
PORTAL_FIXTURE_MODULES = ["core", "archive"]


def sha256(value):
    if not isinstance(value, bytes):
        value = json.dumps(value, sort_keys=True).encode()
    return hashlib.sha256(value).hexdigest()


def git(root, *args):
    result = subprocess.run(["git", "-C", str(root), *args], text=True,
                            capture_output=True, check=False)
    if result.returncode:
        raise RuntimeError((result.stderr or result.stdout).strip())
    return result.stdout.strip()


def verify_portal_runtime(source_root, runtime_root, revision):
    source_root, runtime_root = source_root.resolve(), runtime_root.resolve()
    if revision != PINNED_PORTAL_REVISION or git(source_root, "rev-parse", "HEAD") != revision:
        raise RuntimeError("Portal source does not match the frozen ce77 revision")
    if git(source_root, "status", "--porcelain"):
        raise RuntimeError("Portal source view must be clean")
    source_tree = git(source_root, "rev-parse", "HEAD^{tree}")
    if git(runtime_root, "rev-parse", "HEAD^{tree}") != source_tree:
        raise RuntimeError("Portal runtime worktree differs from the frozen source tree")
    if git(runtime_root, "status", "--porcelain"):
        raise RuntimeError("Portal runtime worktree must be clean")
    if sha256((source_root / "package-lock.json").read_bytes()) != sha256((runtime_root / "package-lock.json").read_bytes()):
        raise RuntimeError("Portal dependency lock differs from the frozen source")
    required = [runtime_root / "node_modules/next/package.json", runtime_root / ".next/BUILD_ID",
                runtime_root / ".next/required-server-files.json"]
    if any(not path.is_file() for path in required):
        raise RuntimeError("Portal runtime dependencies or production build are unavailable")
    tracked = git(runtime_root, "ls-files", "app", "public", "package.json", "package-lock.json",
                  "next.config.ts", "tsconfig.json").splitlines()
    newest_input = max((runtime_root / name).stat().st_mtime for name in tracked if (runtime_root / name).is_file())
    if (runtime_root / ".next/BUILD_ID").stat().st_mtime < newest_input:
        raise RuntimeError("Portal production build predates its exact-tree runtime inputs")
    return {"source_revision": revision, "source_tree": source_tree,
            "build_id": (runtime_root / ".next/BUILD_ID").read_text().strip(),
            "next_version": json.loads(required[0].read_text())["version"]}


def verify_package(package, packet_path):
    package, packet_path = package.resolve(), packet_path.resolve()
    metadata = json.loads((package / "package.json").read_text())
    checksums = json.loads((package / "checksums.json").read_text())
    for relative, expected in checksums.items():
        path = (package / relative).resolve()
        if not path.is_relative_to(package) or not path.is_file() or sha256(path.read_bytes()) != expected:
            raise RuntimeError("Docs package checksum failed: " + relative)
    packet = json.loads(packet_path.read_text())
    if packet.get("schemaVersion") != 1 or packet.get("packageId") != metadata.get("package_id"):
        raise RuntimeError("Portal packet does not identify the supplied Docs package")
    if packet.get("sourceRevision") != metadata.get("source_revision"):
        raise RuntimeError("Portal packet source revision differs from the Docs package")
    if packet.get("organizationId") != "org_a" or packet.get("systemId") != "sys_a":
        raise RuntimeError("Portal packet must target only the local org_a/sys_a fixture")
    guides = packet.get("guides") or []
    if len(guides) != 1 or guides[0].get("id") != GUIDE_ID:
        raise RuntimeError("Portal packet must contain exactly the captured search-collection guide")
    guide = guides[0]
    if guide.get("captureStatus") != "verified-synthetic" or len(guide.get("images") or []) != 3:
        raise RuntimeError("Portal packet must contain three verified synthetic screenshots")
    if OVERRIDE_MARKER not in json.dumps(guide.get("overrides") or {}):
        raise RuntimeError("Portal packet lost the deployment-specific ARCHIVE-DOCS override")
    image_hashes = {}
    for image in guide["images"]:
        raw = base64.b64decode(image["base64"], validate=True)
        if not raw.startswith(b"\x89PNG\r\n\x1a\n") or sha256(raw) != image.get("sha256"):
            raise RuntimeError("Portal packet screenshot bytes do not match their PNG hash")
        image_hashes[image["name"]] = image["sha256"]
    if len(image_hashes) != 3:
        raise RuntimeError("Portal packet screenshot names must be unique")
    deployment_id = packet["deployment"]["id"]
    manifest = json.loads((package / "deployments" / deployment_id / "deployment.json").read_text())
    if sha256(manifest) != packet["deployment"].get("manifestSha256"):
        raise RuntimeError("Portal packet manifest hash differs from the package")
    verify_deployment_profile(packet["deployment"], manifest)
    packaged = package / "deployments" / deployment_id
    if OVERRIDE_MARKER not in (packaged / f"{GUIDE_ID}.md").read_text():
        raise RuntimeError("Generated deployment guide lost the ARCHIVE-DOCS override")
    for name, expected in image_hashes.items():
        if sha256((packaged / "screenshots" / name).read_bytes()) != expected:
            raise RuntimeError("Portal packet screenshot differs from the package: " + name)
    for name in ("LICENSE", "COPYING", "NOTICE"):
        if not (package / name).is_file():
            raise RuntimeError("Docs package is missing " + name)
    if "GNU GENERAL PUBLIC LICENSE" not in packet["license"]["copying"]:
        raise RuntimeError("Portal packet is missing GPL-3.0 license text")
    return packet, image_hashes


def verify_deployment_profile(deployment, manifest):
    if (deployment.get("version") != manifest.get("version") or
            deployment.get("modules") != manifest.get("modules") or
            deployment.get("modules") != PORTAL_FIXTURE_MODULES):
        raise RuntimeError("Portal packet version or module profile differs from the accepted deployment")


def fixture_system_profile(packet):
    if (packet.get("organizationId") != PORTAL_FIXTURE_ORGANIZATION or
            packet.get("systemId") != PORTAL_FIXTURE_SYSTEM):
        raise RuntimeError("Portal fixture setup is restricted to org_a/sys_a")
    deployment = packet.get("deployment") or {}
    version, modules = deployment.get("version"), deployment.get("modules")
    if not isinstance(version, str) or not version or modules != PORTAL_FIXTURE_MODULES:
        raise RuntimeError("Portal fixture setup requires the accepted Core version and module profile")
    return {"version": version, "modules_json": modules}


def require_loopback_origin(origin):
    parsed = urllib.parse.urlsplit(origin)
    identity = (parsed.scheme, parsed.hostname, parsed.path, parsed.query, parsed.fragment)
    if identity != ("http", "127.0.0.1", "", "", "") or parsed.port is None:
        raise RuntimeError("Portal fixture setup requires an explicit 127.0.0.1 HTTP origin")
    return origin


def loopback_json(origin, method, path, body=None):
    require_loopback_origin(origin)
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(origin + path, data=data, method=method,
        headers={"content-type": "application/json", "prefer": "return=representation"})
    with urllib.request.urlopen(request, timeout=2) as response:
        raw = response.read()
    return json.loads(raw) if raw else None


def configure_fixture_system(origin, packet, transport=loopback_json):
    require_loopback_origin(origin)
    profile = fixture_system_profile(packet)
    organization_path = "/rest/v1/organizations?id=eq.org_a"
    system_path = "/rest/v1/systems?id=eq.sys_a&organization_id=eq.org_a"
    organizations = transport(origin, "GET", organization_path)
    systems = transport(origin, "GET", system_path)
    if len(organizations or []) != 1 or organizations[0].get("id") != PORTAL_FIXTURE_ORGANIZATION or \
            organizations[0].get("name") != PORTAL_FIXTURE_NAME:
        raise RuntimeError("Portal mock does not expose the expected synthetic org_a fixture")
    if len(systems or []) != 1 or systems[0].get("id") != PORTAL_FIXTURE_SYSTEM or \
            systems[0].get("organization_id") != PORTAL_FIXTURE_ORGANIZATION or \
            systems[0].get("name") != PORTAL_FIXTURE_NAME:
        raise RuntimeError("Portal mock does not expose the expected synthetic sys_a fixture")
    updated = transport(origin, "PATCH", system_path, profile)
    if len(updated or []) != 1:
        raise RuntimeError("Portal mock refused the exact synthetic system profile update")
    readback = transport(origin, "GET", system_path)
    if len(readback or []) != 1 or any(readback[0].get(key) != value for key, value in profile.items()):
        raise RuntimeError("Portal mock system profile readback differs from the accepted packet")
    return profile


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def ready(url, process):
    for _ in range(100):
        if process.poll() is not None:
            raise RuntimeError("Synthetic Portal process exited; inspect the private logs")
        try:
            urllib.request.urlopen(url, timeout=1).close()
            return
        except Exception:
            time.sleep(0.1)
    raise RuntimeError("Synthetic Portal process did not become ready")


def browser_sha(page, url):
    return page.evaluate("""url => fetch(url).then(async response => {
      if (!response.ok) throw new Error(`private image ${response.status}`);
      const bytes = await response.arrayBuffer();
      const hash = await crypto.subtle.digest('SHA-256', bytes);
      return Array.from(new Uint8Array(hash)).map(value => value.toString(16).padStart(2,'0')).join('');
    })""", url)


def source_revision_metadata(docs, source_revision):
    return docs.locator(".support-docs-footer details code").get_by_text(
        source_revision, exact=True)


def run(args):
    portal_identity = verify_portal_runtime(args.portal_source, args.portal_runtime, args.portal_revision)
    packet, image_hashes = verify_package(args.package, args.packet)
    args.output.mkdir(parents=True, exist_ok=False)
    dbport, port = free_port(), free_port()
    base = f"http://127.0.0.1:{port}"
    env = {key: value for key, value in os.environ.items()
           if key in {"PATH", "LANG", "LC_ALL", "TZ", "HOME", "TMPDIR"}}
    env.update({
        "MOCK_SUPABASE_PORT": str(dbport), "MOCK_SUPPORT_DOCS": "true",
        "MOCK_ADMIN_PASSWORD": "synthetic-admin-only", "MOCK_CLIENT_PASSWORD": "synthetic-client-only",
        "SUPABASE_URL": f"http://127.0.0.1:{dbport}", "SUPABASE_SERVICE_ROLE_KEY": "synthetic-service-role",
        "VAULTLINE_SESSION_SECRET": "synthetic-session-signing-key-for-docs-only-0001",
        "VAULTLINE_LOGIN_THROTTLE_SECRET": "synthetic-throttle-key-for-docs-only-0002",
        "VAULTLINE_ADMIN_EMAILS": "docs-admin@example.test",
    })
    logs = [(args.output / "mock.log").open("w"), (args.output / "portal.log").open("w")]
    processes = []
    try:
        db = subprocess.Popen(["node", "scripts/mock-supabase.mjs"], cwd=args.portal_runtime,
                              env=env, stdout=logs[0], stderr=subprocess.STDOUT)
        processes.append(db)
        ready(f"http://127.0.0.1:{dbport}/rest/v1/organizations", db)
        configure_fixture_system(f"http://127.0.0.1:{dbport}", packet)
        app = subprocess.Popen(["node", "node_modules/next/dist/bin/next", "start", "--hostname",
                                "127.0.0.1", "--port", str(port)], cwd=args.portal_runtime,
                               env=env, stdout=logs[1], stderr=subprocess.STDOUT)
        processes.append(app)
        ready(base, app)
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            contexts = []

            def login(email, password):
                context = browser.new_context(viewport={"width": 1440, "height": 1000})
                contexts.append(context)
                context.route("**/*", lambda route: route.continue_()
                              if route.request.url.startswith(base + "/") else route.abort())
                page = context.new_page()
                page.set_default_timeout(12000)
                page.goto(base)
                page.get_by_label("Email", exact=True).fill(email)
                page.get_by_label("Password", exact=True).fill(password)
                page.get_by_role("button", name="Sign in", exact=True).click()
                expect(page.locator(".sidebar")).to_be_visible()
                return page

            def support_guides(page):
                page.goto(base)
                page.get_by_role("button", name="Support guides", exact=True).click()
                return page.locator("[data-testid=support-docs]")

            admin = login("docs-admin@example.test", "synthetic-admin-only")
            client_a = login("docs-a@example.test", "synthetic-client-only")
            client_b = login("docs-b@example.test", "synthetic-client-only")
            admin.locator(".cli").filter(has_text="Synthetic Studio").click()
            expect(admin.get_by_role("heading", name="Client support documentation", exact=True)).to_be_visible()
            docs = admin.locator("[data-testid=support-docs]")
            docs.get_by_label("Import draft package").set_input_files(str(args.packet))
            expect(docs.get_by_label("Documentation version")).to_be_visible()
            docs.get_by_text("Version and source details", exact=True).click()
            expect(source_revision_metadata(docs, packet["sourceRevision"])).to_be_visible()
            expect(support_guides(client_a).get_by_text("No guides published yet", exact=True)).to_be_visible()
            revision = admin.evaluate("fetch('/api/support-docs?organizationId=org_a').then(r=>r.json())")["revisions"][0]["id"]
            denied_revision = client_b.evaluate("url=>fetch(url).then(r=>r.status)",
                f"/api/support-docs/revision?revisionId={revision}&organizationId=org_a")
            if denied_revision != 404:
                raise RuntimeError("cross-client draft revision was not denied")
            docs.get_by_label("Review note", exact=True).fill(
                "Verified exact Core source, effective config, persistence proof, screenshots and deployment override.")
            docs.locator("input[type=checkbox]").check()
            docs.get_by_role("button", name="Publish to client", exact=True).click()
            expect(docs.get_by_text("Published", exact=True)).to_be_visible()
            client_docs = support_guides(client_a)
            expect(client_docs.get_by_role("heading", name=GUIDE_TITLE, exact=True).first).to_be_visible()
            if OVERRIDE_MARKER not in client_docs.inner_text():
                raise RuntimeError("client rendering lost the deployment override")
            images = client_docs.locator("img")
            if images.count() != 3:
                raise RuntimeError("published guide did not render exactly three private images")
            for image in images.all():
                src = image.get_attribute("src")
                name = src.split("image=", 1)[1]
                from urllib.parse import unquote
                name = unquote(name)
                if browser_sha(client_a, src) != image_hashes[name]:
                    raise RuntimeError("private Portal image bytes differ from the captured package")
            first_name = next(iter(image_hashes))
            denied_image = client_b.evaluate("url=>fetch(url).then(r=>r.status)",
                f"/api/support-docs/image?revisionId={revision}&organizationId=org_a&guideId={GUIDE_ID}&image={first_name}")
            denied_download = client_b.evaluate("url=>fetch(url).then(r=>r.status)",
                f"/api/support-docs/download?revisionId={revision}&organizationId=org_a")
            if (denied_image, denied_download) != (404, 404):
                raise RuntimeError("cross-client image or package download was not denied")
            with client_a.expect_download() as pending:
                client_docs.get_by_role("link", name="Download all guides & screenshots", exact=True).click()
            archive_path = args.output / "client-guides.zip"
            pending.value.save_as(str(archive_path))
            with zipfile.ZipFile(archive_path) as archive:
                names = archive.namelist()
                if len([name for name in names if name.endswith(".md")]) != 1:
                    raise RuntimeError("Portal ZIP does not contain exactly one Markdown guide")
                if len([name for name in names if name.endswith(".png")]) != 3:
                    raise RuntimeError("Portal ZIP does not contain exactly three screenshots")
                if OVERRIDE_MARKER not in archive.read(f"{GUIDE_ID}/{GUIDE_ID}.md").decode():
                    raise RuntimeError("Portal ZIP lost the deployment override")
                if b"GNU GENERAL PUBLIC LICENSE" not in archive.read("COPYING.txt"):
                    raise RuntimeError("Portal ZIP lost GPL-3.0 license text")
            docs.get_by_label("Review note", exact=True).fill("Withdraw exact synthetic qualification publication.")
            docs.locator("input[type=checkbox]").check()
            docs.get_by_role("button", name="Withdraw published guides", exact=True).click()
            expect(support_guides(client_a).get_by_text("No guides published yet", exact=True)).to_be_visible()
            for context in contexts:
                context.close()
            browser.close()
        receipt = {
            "result": "pass", "portal": portal_identity,
            "package_id": packet["packageId"], "source_revision": packet["sourceRevision"],
            "guide_id": GUIDE_ID, "image_sha256": image_hashes,
            "checks": ["draft invisible", "review and local synthetic publication", "client rendering",
                       "three private image hashes", "one-guide ZIP with GPL notices and override",
                       "cross-client revision image and download denial", "withdrawal"],
            "hosted_write": False, "client_publication": False,
        }
        (args.output / "receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
        print(json.dumps(receipt, indent=2, sort_keys=True))
    finally:
        for process in reversed(processes):
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        for log in logs:
            log.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--portal-source", type=Path, required=True)
    parser.add_argument("--portal-runtime", type=Path, required=True)
    parser.add_argument("--portal-revision", default=PINNED_PORTAL_REVISION)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
