# Core 1.0.158 capture correction candidate

This successor corrects the five findings in the distinct review of `2c15d384`. It remains frozen
for distinct review before any runtime, browser, capture or Portal operation. It serves the real
Core backend and generated frontend from signed source
`98a373276de75fcf9510dfb02ffb89778b8ea324`. It does not use the Vaultline Docs screenshot fixture.

## Frozen inputs

- Docs base: `383faa73cc0f00fdfffe24118654f0713f0eef31`
- Core version and source: `1.0.158`, `98a373276de75fcf9510dfb02ffb89778b8ea324`
- Core source view: `/Users/jakehalperin/Developer/Vaultline/worktrees/core/vlp-2189-docs-capture-source`
- Recipes: `examples/media-nexus-core-1.0.158-recipes.json`
- Deployment: `examples/deployments/core-1.0.158-docs.json`
- Guide: `search-collection` only
- Manifest and effective-config projection SHA-256: `9a56c2768e445225528bd2185a3f15073952179960ae4e43b1d3dd25fd7c62af`
- Guide evidence/action binding: `58d4452cce4d772c83abe3759a97a281f1df8ab11b89a039b8579245536f3f48`
- Synthetic source-locator SHA-256: `5931da49bb3534bbfa560558631145d0d7253a7221900103ef17eef9ff273259`

The manifest carries `core` and `archive`, version `1.0.158`, a stable projection of the actual
effective Core configuration, and a separately stored `ARCHIVE-DOCS-` deployment note. The harness
loads the configuration with pinned Core's own schema and refuses any difference between the
effective projection and manifest. The deployment remains an uninstalled synthetic source test:
`product.generated` is false and no commissioned profile or access origin is claimed. Generation
keeps the shared guide and override separate. The package continues to include `LICENSE`, `COPYING`,
`NOTICE`, source metadata and checksums.

Before importing Core, the serve process starts with `-B`, replaces its environment with a closed set,
sets `sys.dont_write_bytecode` and binds `sys.pycache_prefix` to the private cache root: interpreter
and locale inputs plus private `HOME`, `TMPDIR`, config, database, derivative, cache and node paths.
Ambient deployment, signed-runtime, site-overlay, access-state, provider and credential selectors
are not copied or read. A focused regression supplies hostile selector paths and confirms they are
absent from the effective Core configuration.

## Reviewable source-only check

This command validates the clean exact Core checkout, source version, recipe anchors, manifest,
one-guide boundary and planned runtime envelope. It does not start Core or a browser and does not
create the runtime root.

```bash
.venv/bin/python scripts/core_capture_harness.py inspect \
  --core-root /Users/jakehalperin/Developer/Vaultline/worktrees/core/vlp-2189-docs-capture-source \
  --revision 98a373276de75fcf9510dfb02ffb89778b8ea324 \
  --recipes examples/media-nexus-core-1.0.158-recipes.json \
  --manifest examples/deployments/core-1.0.158-docs.json \
  --root /Users/jakehalperin/Developer/Vaultline/dev/docs-capture/vlp-2189-capture-attempt2
```

The reported 2 GiB root growth, 2 GiB RSS and 32 processes are planning envelopes for entry and
terminal measurement, not enforced quotas. Browser work is one serial private headless job. Task8
must recheck the active VLP-2189 claim, free space, current process/memory use, the unused private
root, clean exact Core source, and a free OS-assigned loopback port before execution.

The source-only correction check is:

```bash
VAULTLINE_DOCS_CORE_ROOT=/Users/jakehalperin/Developer/Vaultline/worktrees/core/vlp-2189-docs-capture-source \
  .venv/bin/python -m unittest tests.test_core_capture -v
```

It runs focused tests, including the real pinned Core config loader, without importing the Core
server or starting a listener. The Docs virtual environment is Python 3.9.6 and supplies Playwright,
Markdown, ReportLab and Pillow. It does not supply Flask or Werkzeug, so the Core server command is
bound separately to the existing `/usr/bin/python3` environment. That interpreter supplies Flask,
Werkzeug, Waitress and Faster Whisper used by this bounded path; its missing optional `segno` module
is imported only by the unexercised mobile QR function and is not installed by this phase.

## Reviewed runtime sequence for Task8

After distinct source acceptance, Task8 may run the following in a private terminal. `serve` binds
the real Core Flask application to loopback port `0`, records the assigned port, PID, start UID,
source/config identity and environment variable names in `control/ready.json`, and stops on
SIGTERM or SIGINT. The random test password remains in process memory; the disposable database has
only the `docs-reviewer` test account and synthetic media. No client or installed Media Nexus state
is read.

The failed first-attempt root at
`/Users/jakehalperin/Developer/Vaultline/dev/docs-capture/vlp-2189-review` remains preserved with its
logs and failure evidence. Attempt two uses the separate unused root below.

```bash
ROOT=/Users/jakehalperin/Developer/Vaultline/dev/docs-capture/vlp-2189-capture-attempt2
/usr/bin/python3 -B scripts/core_capture_harness.py serve \
  --core-root /Users/jakehalperin/Developer/Vaultline/worktrees/core/vlp-2189-docs-capture-source \
  --revision 98a373276de75fcf9510dfb02ffb89778b8ea324 \
  --recipes examples/media-nexus-core-1.0.158-recipes.json \
  --manifest examples/deployments/core-1.0.158-docs.json \
  --root "$ROOT"
```

In a second private terminal, after checking `ready.json` and retaining its exact URL:

```bash
ROOT=/Users/jakehalperin/Developer/Vaultline/dev/docs-capture/vlp-2189-capture-attempt2
CORE_URL="$(python3 -c 'import json; print(json.load(open("/Users/jakehalperin/Developer/Vaultline/dev/docs-capture/vlp-2189-capture-attempt2/control/ready.json"))["url"])')"
.venv/bin/python -m vaultline_docs generate \
  --repo /Users/jakehalperin/Developer/Vaultline/worktrees/core/vlp-2189-docs-capture-source \
  --revision 98a373276de75fcf9510dfb02ffb89778b8ea324 \
  --recipes examples/media-nexus-core-1.0.158-recipes.json \
  --manifest examples/deployments/core-1.0.158-docs.json \
  --test-url "core-1-0-158-docs=$CORE_URL" \
  --output "$ROOT/packages"
```

The expected browser journey searches for `Ridge Sunrise.mp4`, selects that real Core result,
creates `ARCHIVE-DOCS-SELECTS`, and opens that collection. Each screenshot is retained only after
authenticated `/api/me`, healthy summary-only `/api/bootstrap/v2`, and bounded live
`/api/assets/v3?limit=10` response prove the seeded asset is served by Core and `API.live` is true.
Any `(demo)` result is refused. From step two onward, the loopback proof route reads Core's
persisted `collections`, `collection_assets`, and `assets` rows and requires the exact member ID,
note, one-member count, and unchanged source-locator digest. The final UI assertion is scoped to the
opened collection breadcrumb and `#asset-card-docs-ridge-sunrise`. Missing proof, selector, identity,
network origin, or expected result withholds the screenshot and package.

## Portal acceptance after Core capture

Use the generated package ID and export an immutable packet for the existing local synthetic
`org_a` / `sys_a` Portal fixture:

```bash
.venv/bin/python -m vaultline_docs portal-export \
  --package "$ROOT/packages/PACKAGE_ID" \
  --deployment core-1-0-158-docs \
  --organization-id org_a --system-id sys_a \
  --output "$ROOT/core-1.0.158.portal.json"
```

Task8 must use the clean Portal source view
`/Users/jakehalperin/Developer/Vaultline/worktrees/client-portal/vlp-2189-docs-portal-source` at
`ce77a0ce867e5229d9fdef9f94179cc048c2d3d3`. The clean runtime worktree at
`/Users/jakehalperin/Developer/Vaultline/worktrees/client-portal/vlp-1971-vaultline-docs` has the
same exact Git tree `9670af892d9e4f19d23767f0278c236eecc2773a`, existing Next 16.3.8 dependencies,
and production build ID `uhooKsARJDvfuKZoN1CvP`. The qualifier refuses a dirty checkout, a tree or
lock mismatch, missing build files, or a build older than its tracked runtime inputs.

After screenshot review, run the focused package-specific flow with fresh output:

```bash
ROOT=/Users/jakehalperin/Developer/Vaultline/dev/docs-capture/vlp-2189-capture-attempt2
PACKAGE="$ROOT/packages/PACKAGE_ID"
PACKET="$ROOT/core-1.0.158.portal.json"
.venv/bin/python scripts/qualify_core_guide_portal.py \
  --portal-source /Users/jakehalperin/Developer/Vaultline/worktrees/client-portal/vlp-2189-docs-portal-source \
  --portal-runtime /Users/jakehalperin/Developer/Vaultline/worktrees/client-portal/vlp-1971-vaultline-docs \
  --portal-revision ce77a0ce867e5229d9fdef9f94179cc048c2d3d3 \
  --package "$PACKAGE" --packet "$PACKET" \
  --output "$ROOT/portal-qualification"
```

The script accepts only the actual one-guide packet and verifies package checksums, source/package/
manifest identity, three PNG hashes, the preserved `ARCHIVE-DOCS-` note, and GPL notices before it
starts the existing local Portal fixture. Its browser flow proves draft invisibility, administrator
review, local synthetic publication, client rendering, private image bytes, a one-guide/three-image
ZIP, cross-client revision/image/download denial, and withdrawal. It never targets a hosted Portal.
This flow has not run; the distinct reviewer must accept this exact source first. The existing hosted
migration, production deployment and authenticated readback are already qualified and are not repeated.

Stop the owned Core process, confirm its PID and listener are gone, retain `control/stopped.json`,
record actual root growth/RSS/process peaks, and release the unused private root only after evidence
is copied. This phase does not authorize hosted writes, client publication or customer messages.
