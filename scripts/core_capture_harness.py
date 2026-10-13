#!/usr/bin/env python3
"""Serve one exact Core checkout with isolated synthetic state for Docs capture.

This is a test-only launcher. It imports and serves Core's real Flask application and generated
frontend, adds only the identity/session routes required by Vaultline Docs, and seeds a disposable
database with synthetic media. It never installs Core or writes to an installed/client tree.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import secrets
import signal
import subprocess
import sys
import threading
import tempfile

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))


EXPECTED_CORE_REVISION = "98a373276de75fcf9510dfb02ffb89778b8ea324"
EXPECTED_CORE_VERSION = "1.0.158"
TEST_ACCOUNT = "docs-reviewer"
MAX_ROOT_BYTES = 2 * 1024 * 1024 * 1024
ASSET_ID = "docs-ridge-sunrise"
ASSET_SOURCE_PATH = "/synthetic/docs/Ridge Sunrise.mp4"
COLLECTION_NAME = "ARCHIVE-DOCS-SELECTS"
COLLECTION_NOTE = "Synthetic documentation review only"


class HarnessError(RuntimeError):
    pass


from vaultline_docs.source import digest


def read_json(path):
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise HarnessError(f"expected JSON object: {path}")
    return value


def git(core, *args):
    result = subprocess.run(["git", "-C", str(core), *args], text=True,
                            capture_output=True, check=False)
    if result.returncode:
        raise HarnessError((result.stderr or result.stdout).strip())
    return result.stdout.strip()


def validate_inputs(core, revision, recipes_path, manifest_path, root):
    core = Path(core).resolve()
    root = Path(root).resolve()
    if revision != EXPECTED_CORE_REVISION:
        raise HarnessError("the harness is frozen to signed Core 1.0.158 source " + EXPECTED_CORE_REVISION)
    if git(core, "rev-parse", "HEAD") != revision:
        raise HarnessError("Core checkout does not match the frozen revision")
    if git(core, "status", "--porcelain"):
        raise HarnessError("Core checkout must be clean; the canonical dirty checkout is forbidden")
    product = read_json(core / "product/product.json")
    if product.get("coreVersion") != EXPECTED_CORE_VERSION:
        raise HarnessError("Core product version does not match 1.0.158")
    manifest = read_json(manifest_path)
    if manifest.get("synthetic") is not True:
        raise HarnessError("deployment manifest must be explicitly synthetic")
    if manifest.get("version") != EXPECTED_CORE_VERSION:
        raise HarnessError("deployment version does not match Core")
    if manifest.get("modules") != ["core", "archive"]:
        raise HarnessError("this bounded harness permits only core and archive")
    recipes = read_json(recipes_path)
    if [item.get("id") for item in recipes.get("guides", [])] != ["search-collection"]:
        raise HarnessError("this phase permits exactly the search-collection guide")
    home = Path.home().resolve()
    if root == home or home not in root.parents:
        raise HarnessError("private runtime root must be beneath the current user home")
    installed = home / "Library/Application Support/Vaultline"
    if root == installed or installed in root.parents:
        raise HarnessError("private runtime root overlaps installed Media Nexus state")
    if root.exists() and any(root.iterdir()):
        raise HarnessError("private runtime root must be new or empty")
    return core, root, recipes, manifest


def manifest_config_from_effective(config):
    """Project the tested Core config into the stable Docs deployment contract."""
    return {
        # These stable aliases are the existing Docs eligibility interface.
        "collections": config["features"]["collections"],
        "remoteTransfer": config["features"]["remoteTransfer"],
        "coreEffective": {
            "product": {
                "generated": config["product"]["generated"],
                "coreVersion": config["product"]["coreVersion"],
                "environment": config["product"]["environment"],
                "modules": config["product"]["modules"],
            },
            "client": {"deployment": config["client"]["deployment"]},
            "features": {
                key: config["features"][key]
                for key in (
                    "collections", "publicRead", "relay", "photo", "review", "post", "brand",
                    "tagging", "transcription", "nlSearch", "advancedSearch", "remoteTransfer",
                    "fileTransfers",
                )
            },
            "storage": {"autoIndex": config["storage"]["autoIndex"], "roots": config["storage"]["roots"]},
        },
    }


def runtime_environment(root, config_path, inherited=None):
    """Return a closed environment without inspecting or copying credential values."""
    inherited = os.environ if inherited is None else inherited
    env = {}
    for name in ("PATH", "LANG", "LC_ALL", "TZ", "SYSTEMROOT"):
        if name in inherited:
            env[name] = inherited[name]
    env.update({
        "HOME": str(root / "home"),
        "TMPDIR": str(root / "tmp"),
        "VAULTLINE_CONFIG_PATH": str(config_path),
        "VAULTLINE_DATABASE_HOME": str(root / "database"),
        "VAULTLINE_DERIVATIVE_HOME": str(root / "derivatives"),
        "VAULTLINE_NODE_ID": "docs-node",
        "VAULTLINE_MEDIA_ORIGINALS_CONFIGURED": "false",
        "VAULTLINE_NONINTERACTIVE": "1",
        "VAULTLINE_SKIP_OLLAMA": "1",
        "PYTHONPYCACHEPREFIX": str(root / "cache"),
        "PYTHONDONTWRITEBYTECODE": "1",
    })
    return env


def load_effective_config(core, root, config_path, inherited=None):
    """Import only pinned Core's config module in a closed synthetic subprocess."""
    script = (
        "import json,sys;sys.path.insert(0,sys.argv[1]);"
        "import vaultline_config as c;"
        "print(json.dumps(c.CONFIG,sort_keys=True))"
    )
    result = subprocess.run(
        [sys.executable, "-c", script, str(core)],
        cwd=core,
        env=runtime_environment(root, config_path, inherited),
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        raise HarnessError("pinned Core rejected the synthetic runtime configuration")
    try:
        return json.loads(result.stdout.strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError) as error:
        raise HarnessError("pinned Core did not return an effective configuration") from error


def validate_effective_identity(effective, manifest):
    projected = manifest_config_from_effective(effective)
    if projected != manifest.get("config"):
        raise HarnessError("deployment manifest config differs from pinned Core effective configuration")
    if effective["product"]["coreVersion"] != manifest["version"]:
        raise HarnessError("effective Core version differs from deployment manifest")
    if effective["product"]["modules"] != manifest["modules"]:
        raise HarnessError("effective Core modules differ from deployment manifest")
    return projected


def plan(core, revision, recipes_path, manifest_path, root, *, check_effective=True):
    core, root, recipes, manifest = validate_inputs(
        core, revision, recipes_path, manifest_path, root)
    from vaultline_docs.source import Source, load_guides
    guides, blocked, bindings = load_guides(Source(core, revision), recipes)
    if blocked or [item["id"] for item in guides] != ["search-collection"]:
        raise HarnessError("Core source does not satisfy the frozen guide evidence: " + json.dumps(blocked))
    if check_effective:
        with tempfile.TemporaryDirectory(prefix="vaultline-docs-config-") as temp:
            config_root = Path(temp)
            for name in ("database", "derivatives", "home", "tmp", "cache"):
                (config_root / name).mkdir(mode=0o700)
            config_path = config_root / "runtime-config.json"
            write_private(config_path, runtime_config(config_root))
            effective = load_effective_config(core, config_root, config_path)
            validate_effective_identity(effective, manifest)
    return {
        "source_revision": revision,
        "version": manifest["version"],
        "modules": manifest["modules"],
        "platform": manifest["platform"],
        "config_sha256": digest(manifest.get("config", {})),
        "contracts": bindings,
        "synthetic": True,
        "test_account": TEST_ACCOUNT,
        "capture_session": {"mode": "endpoint", "method": "GET",
                            "path": "/__vaultline_docs/session"},
        "capture_proof": {"method": "GET", "path": "/__vaultline_docs/proof",
                          "after_step": 2, "collection": COLLECTION_NAME,
                          "asset_id": ASSET_ID,
                          "source_path_sha256": digest(ASSET_SOURCE_PATH.encode())},
        "guide_ids": ["search-collection"],
        "core_root": str(core),
        "private_root": str(root),
        "port": 0,
        "process_plan": 32,
        "rss_plan_bytes": 2 * 1024 * 1024 * 1024,
        "root_growth_plan_bytes": MAX_ROOT_BYTES,
        "headless_jobs": 1,
    }


def runtime_config(root):
    return {
        "product": {"generated": False, "profileId": "vaultline-docs-core-1-0-158",
                    "profileSchemaVersion": "synthetic-test-only", "coreVersion": EXPECTED_CORE_VERSION,
                    "profileHash": "", "environment": "development",
                    "modules": ["core", "archive"], "capabilities": []},
        "client": {"name": "Vaultline Docs Synthetic", "tagline": "Synthetic documentation review",
                   "deployment": "Uninstalled source test"},
        "branding": {"badge": "Docs Synthetic"},
        "features": {"collections": True, "publicRead": False, "relay": False,
                     "photo": False, "review": False, "post": False, "brand": False,
                     "tagging": False, "transcription": False, "nlSearch": False,
                     "advancedSearch": True, "remoteTransfer": False, "fileTransfers": False},
        "storage": {"autoIndex": False, "databaseHome": str(root / "database"),
                    "derivativeHome": str(root / "derivatives"), "roots": []},
    }


def write_private(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.chmod(path, 0o600)


def serve(args):
    identity = plan(args.core_root, args.revision, args.recipes, args.manifest, args.root,
                    check_effective=False)
    root = Path(identity["private_root"])
    root.mkdir(parents=True, mode=0o700)
    os.chmod(root, 0o700)
    for name in ("database", "derivatives", "media", "control", "cache", "images", "home", "tmp"):
        (root / name).mkdir(mode=0o700)
    config_path = root / "control/runtime-config.json"
    write_private(config_path, runtime_config(root))
    closed_env = runtime_environment(root, config_path)
    os.environ.clear()
    os.environ.update(closed_env)
    sys.path.insert(0, identity["core_root"])
    import vaultline_config as core_config
    manifest = read_json(args.manifest)
    effective_projection = validate_effective_identity(core_config.CONFIG, manifest)
    identity["config_sha256"] = digest(effective_projection)
    import vaultline_db as db
    import vaultline_server as server

    password = secrets.token_urlsafe(32)
    db.init_db()
    con = db.connect()
    try:
        if not con.execute("SELECT 1 FROM users WHERE username=?", (TEST_ACCOUNT,)).fetchone():
            db.create_user(con, TEST_ACCOUNT, password, "editor", display_name="Docs Reviewer")
        db.upsert_volume(con, {"id": "docs-volume", "label": "Synthetic Ridge Archive",
                              "kind": "Test", "mount": "/synthetic/docs", "online": 1})
        media = root / "media/Ridge Sunrise.mp4"
        media.write_bytes(b"Vaultline Docs synthetic media; no client content.\n")
        db.upsert_asset(con, {"id": ASSET_ID, "name": media.name,
            "volume_id": "docs-volume", "folder": "Ridge/Selects",
            "path": ASSET_SOURCE_PATH,
            "ext": "mp4", "media_type": "video", "classification": "Camera Original",
            "size_bytes": media.stat().st_size, "duration_sec": 12, "indexed_at": db.now(),
            "availability": "online", "proxy_status": "None", "transcript_status": "None"})
        con.commit()
    finally:
        con.close()

    @server.app.get("/__vaultline_docs")
    def vaultline_docs_identity():
        from flask import jsonify
        return jsonify({key: value for key, value in identity.items()
                        if key not in {"guide_ids", "core_root", "private_root", "port",
                                       "process_plan", "rss_plan_bytes", "root_growth_plan_bytes",
                                       "headless_jobs"}})

    @server.app.get("/__vaultline_docs/session")
    def vaultline_docs_session():
        from flask import jsonify, request
        if request.remote_addr not in {"127.0.0.1", "::1"}:
            return jsonify({"error": "loopback only"}), 403
        con = db.connect()
        try:
            user = db.verify_login(con, TEST_ACCOUNT, password)
            if not user:
                return jsonify({"error": "synthetic test account unavailable"}), 503
            token = db.create_session(con, user["id"])
            con.commit()
        finally:
            con.close()
        response = jsonify({"ok": True, "test_account": TEST_ACCOUNT})
        response.set_cookie(server.COOKIE, token, httponly=True, samesite="Lax", path="/")
        return response

    @server.app.get("/__vaultline_docs/proof")
    def vaultline_docs_proof():
        from flask import jsonify, request
        if request.remote_addr not in {"127.0.0.1", "::1"}:
            return jsonify({"error": "loopback only"}), 403
        con = db.connect()
        try:
            asset = con.execute("SELECT id,path FROM assets WHERE id=?", (ASSET_ID,)).fetchone()
            collection = con.execute(
                "SELECT id,name,note FROM collections WHERE name=? ORDER BY created_at DESC LIMIT 1",
                (COLLECTION_NAME,),
            ).fetchone()
            members = [] if not collection else [row["asset_id"] for row in con.execute(
                "SELECT asset_id FROM collection_assets WHERE collection_id=? ORDER BY position,rowid",
                (collection["id"],),
            ).fetchall()]
        finally:
            con.close()
        source_path = asset["path"] if asset else ""
        return jsonify({
            "ui_mode": "live-core",
            "collection": None if not collection else {
                "name": collection["name"], "note": collection["note"],
                "member_ids": members, "member_count": len(members),
            },
            "asset": {"id": asset["id"] if asset else None,
                      "source_path_sha256": digest(source_path.encode()),
                      "source_path_unchanged": source_path == ASSET_SOURCE_PATH},
        })

    from werkzeug.serving import make_server
    httpd = make_server("127.0.0.1", 0, server.app, threaded=True)
    identity["port"] = httpd.server_port
    control = {**identity, "pid": os.getpid(), "start_uid": os.getuid(),
               "url": f"http://127.0.0.1:{httpd.server_port}",
               "runtime_argv": sys.argv, "runtime_env_names": sorted(name for name in os.environ
                 if name.startswith("VAULTLINE_") or name in {"PYTHONPYCACHEPREFIX", "PYTHONDONTWRITEBYTECODE"})}
    write_private(root / "control/ready.json", control)
    stopped = False
    def stop(_signum, _frame):
        nonlocal stopped
        if not stopped:
            stopped = True
            threading.Thread(target=httpd.shutdown, name="docs-harness-stop", daemon=True).start()
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    print(json.dumps({"ready": str(root / "control/ready.json"), "url": control["url"]}), flush=True)
    try:
        httpd.serve_forever()
    finally:
        write_private(root / "control/stopped.json", {"pid": os.getpid(), "stopped": True})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("inspect", "serve"))
    parser.add_argument("--core-root", required=True)
    parser.add_argument("--revision", default=EXPECTED_CORE_REVISION)
    parser.add_argument("--recipes", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--root", required=True)
    args = parser.parse_args()
    try:
        if args.command == "inspect":
            print(json.dumps(plan(args.core_root, args.revision, args.recipes, args.manifest,
                                  args.root), indent=2, sort_keys=True))
        else:
            serve(args)
    except (HarnessError, ValueError, json.JSONDecodeError) as error:
        parser.exit(1, "Core capture harness withheld: " + str(error) + "\n")


if __name__ == "__main__":
    main()
