# Core 1.0.158 capture candidate

This candidate is frozen for distinct review before any runtime, browser, capture or Portal
operation. It serves the real Core backend and generated frontend from signed source
`98a373276de75fcf9510dfb02ffb89778b8ea324`. It does not use the Vaultline Docs screenshot fixture.

## Frozen inputs

- Docs base: `383faa73cc0f00fdfffe24118654f0713f0eef31`
- Core version and source: `1.0.158`, `98a373276de75fcf9510dfb02ffb89778b8ea324`
- Core source view: `/Users/jakehalperin/Developer/Vaultline/worktrees/core/vlp-2189-docs-capture-source`
- Recipes: `examples/media-nexus-core-1.0.158-recipes.json`
- Deployment: `examples/deployments/core-1.0.158-docs.json`
- Guide: `search-collection` only
- Manifest config SHA-256: `03cadeeb0d7a94ea591b72aac77550cbf8b718d26177e25f0e02a1012cc96eda`
- Guide evidence/action binding: `e3f7ea89d3a7f60eab8d4feeaf65246d86925a3b3858912cf9a1dcf84dd54d40`

The manifest carries `core` and `archive`, version `1.0.158`, Collections enabled, remote transfer
disabled and a separately stored `ARCHIVE-DOCS-` deployment note. Generation keeps the shared
guide and that override separate. The normal package continues to include `LICENSE`, `COPYING`,
`NOTICE`, source metadata and checksums.

## Reviewable source-only check

This command validates the clean exact Core checkout, source version, recipe anchors, manifest,
one-guide boundary and planned runtime envelope. It does not start Core or a browser and does not
create the runtime root.

```bash
python3 scripts/core_capture_harness.py inspect \
  --core-root /Users/jakehalperin/Developer/Vaultline/worktrees/core/vlp-2189-docs-capture-source \
  --revision 98a373276de75fcf9510dfb02ffb89778b8ea324 \
  --recipes examples/media-nexus-core-1.0.158-recipes.json \
  --manifest examples/deployments/core-1.0.158-docs.json \
  --root /Users/jakehalperin/Developer/Vaultline/dev/docs-capture/vlp-2189-review
```

The reported 2 GiB root growth, 2 GiB RSS and 32 processes are planning envelopes for entry and
terminal measurement, not enforced quotas. Browser work is one serial private headless job. Task8
must recheck the active VLP-2189 claim, free space, current process/memory use, the unused private
root, clean exact Core source, and a free OS-assigned loopback port before execution.

## Reviewed runtime sequence for Task8

After distinct source acceptance, Task8 may run the following in a private terminal. `serve` binds
the real Core Flask application to loopback port `0`, records the assigned port, PID, start UID,
source/config identity and environment variable names in `control/ready.json`, and stops on
SIGTERM or SIGINT. The random test password remains in process memory; the disposable database has
only the `docs-reviewer` test account and synthetic media. No client or installed Media Nexus state
is read.

```bash
ROOT=/Users/jakehalperin/Developer/Vaultline/dev/docs-capture/vlp-2189-review
python3 scripts/core_capture_harness.py serve \
  --core-root /Users/jakehalperin/Developer/Vaultline/worktrees/core/vlp-2189-docs-capture-source \
  --revision 98a373276de75fcf9510dfb02ffb89778b8ea324 \
  --recipes examples/media-nexus-core-1.0.158-recipes.json \
  --manifest examples/deployments/core-1.0.158-docs.json \
  --root "$ROOT"
```

In a second private terminal, after checking `ready.json` and retaining its exact URL:

```bash
ROOT=/Users/jakehalperin/Developer/Vaultline/dev/docs-capture/vlp-2189-review
CORE_URL="$(python3 -c 'import json; print(json.load(open("/Users/jakehalperin/Developer/Vaultline/dev/docs-capture/vlp-2189-review/control/ready.json"))["url"])')"
.venv/bin/python -m vaultline_docs generate \
  --repo /Users/jakehalperin/Developer/Vaultline/worktrees/core/vlp-2189-docs-capture-source \
  --revision 98a373276de75fcf9510dfb02ffb89778b8ea324 \
  --recipes examples/media-nexus-core-1.0.158-recipes.json \
  --manifest examples/deployments/core-1.0.158-docs.json \
  --test-url "core-1-0-158-docs=$CORE_URL" \
  --output "$ROOT/packages"
```

The expected browser journey searches for `Ridge Sunrise.mp4`, selects that real Core result,
creates `ARCHIVE-DOCS-SELECTS`, and verifies membership in Core's Collections UI. Each of its three
screenshots is retained only after the corresponding UI assertion passes. Any missing selector,
identity mismatch, unexpected network origin, credential field, sensitive path or missing expected
result withholds the package.

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
`ce77a0ce867e5229d9fdef9f94179cc048c2d3d3` and the existing local synthetic fixture. It must
import the generated JSON as a draft, compare/review it, publish only to
that synthetic fixture, and verify client rendering, all three private images, the Markdown/image
ZIP, a cross-client revision/image/download denial, the preserved `ARCHIVE-DOCS-` note and final
withdrawal. It must review the screenshots before accepting them. The existing hosted migration,
production deployment and authenticated readback are already qualified and are not repeated.

Stop the owned Core process, confirm its PID and listener are gone, retain `control/stopped.json`,
record actual root growth/RSS/process peaks, and release the unused private root only after evidence
is copied. This phase does not authorize hosted writes, client publication or customer messages.
