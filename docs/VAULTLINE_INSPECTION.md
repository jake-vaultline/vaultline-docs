# Source and integration inspection - 2026-10-12

## Upstream baseline

Upstream commit: `feb58b6143450f0967aa6e3b4efd776a3cdea94f`.
Fork: https://github.com/jake-vaultline/vaultline-docs.
Authenticated account: jake-vaultline. Existing repository names use vaultline-;
there was no authenticated organization returned, so the fork uses that account.
`upstream` retains maxberko/max-doc-ai and `origin` names the Vaultline fork.
There was no upstream AGENTS.md. README, CONTRIBUTING, config, utilities and five
skill entrypoints were inspected. There is no upstream automated CI workflow.

The architecture is skill orchestration over Python utilities: configuration,
Markdown parsing, inventory and sync-state tracking, browser authentication and
Playwright/Claude/Gemini capture, plus KBProvider implementations for Pylon and
Zendesk. The five skills are capture-screenshots, update-product-doc, sync-docs,
create-changelog and create-release. AI-assisted workflows depend on configured
model access and provider credentials. create-release includes external KB sync;
that is not used by Vaultline's default preview workflow.

Local baseline commands against unchanged upstream utilities:

| Command | Observed result |
| --- | --- |
| `python scripts/kb/sync.py discover` | Pass: 15 demo Markdown documents discovered. |
| `python scripts/utils/markdown.py demo/docs/product_documentation/features/dashboards.md` | Pass: valid structure, 22 headings, 5 placeholder image URLs. Image URLs were not proof of screenshots. |
| `python -m compileall -q scripts utils` | Pass. |
| `python scripts/health_check.py` | 4 checks pass, 7 fail: no config.yaml/.env/provider setup, output config unavailable, skills unregistered. The upstream command exits zero even with failed checks. |
| `python utils/skill_validator.py` | Five skills found with valid structure; zero registered because local settings are absent. |
| Upstream Playwright ScreenshotCapturer, isolated synthetic page | See verification receipt for the unchanged capture utility smoke result. |
| Claude/Gemini paid capture and Pylon/Zendesk writes | Not run: no task-specific API/provider configuration and no publication authorization. |

No provider keys, billing settings or permission files were created to make a
health check green. Upstream tools are preserved; Vaultline adds an offline pipeline.

## Actual license

LICENSE is a short GPL notice, not the complete GPL text. Its grant explicitly says
version 3 or, at the user's option, any later version: GPL-3.0-or-later. It attributes
Copyright (C) 2024 max-doc-ai contributors. The original LICENSE is unchanged.
COPYING is the full license fetched from https://www.gnu.org/licenses/gpl-3.0.txt.
NOTICE identifies the upstream source/baseline and the Vaultline changes. Exported
packages include notices and corresponding generator source. See GPL sections 4-6
for applicable modified-source and non-source distribution conditions.

## Media Nexus

Inspected committed Core source; left its dirty checkout and active work unchanged.
Refreshed origin/main and pinned `282cf8585973c6dcaa2bd5c99d113300886656ec`, whose
`product/product.json` declares Core 1.0.157. Module ownership comes from
`product/modules/archive.json` and `product/modules/relay.json`; operator controls
and recovery text come from `vaultline_app.jsx`. The source-supported recipe emits
line/hash evidence for each guide. The initial guides cover search and collection
creation, Archive remote download, and interruption diagnosis. Drive copying and
advanced destinations are deliberately separate qualification gaps.

Remote downloads are owned by Archive's remoteTransfer flag. Relay is not a
prerequisite for browser download. The original requested "download or transfer"
guide is narrowed to source-supported remote downloading. Core's recovery controls
distinguish Prepare again, Resume save, and Source version required. The fixture
Resume control illustrates pipeline testing, not those real-product semantics.

## Client Portal

Refreshed source revision: `8192371ab58d72a9e88369caa9e9c7d8fbabce1f`.
Inspected `app/support/page.tsx`, `app/lib/documents.ts`,
`app/lib/server/document-attachments.ts`, `app/lib/server/portal-backend.ts`,
`app/api/admin/documents/route.ts`, upload-intent route and `docs/DOCUMENTS.md`.
Support is contact/request guidance. The accessible source uses Documents resources
with one uploaded file or HTTPS link per record, private client-documents storage,
organization-scoped administrator writes, 25 MiB limits and a MIME allowlist.
HTML and ZIP are not accepted attachments; PDF, Markdown and PNG are.

The existing write flow is POST /api/admin/documents/upload-intent, PUT to the
returned signed upload URL, then POST /api/admin/documents. PATCH updates an existing
document. Opening uses GET /api/documents/open with kind/id and a short-lived
signed download URL. The export adapter produces files and an import checklist,
not invented tenant ids, storage keys or a new Portal endpoint.

## Remaining integration gates

- An authenticated Portal administrator test-tenant upload and readback have not
  run. Publication requires Jake's explicit authorization and the correct tenant.
- Real Media Nexus screenshots need a disposable synthetic deployment bound to the
  selected source/config version, a synthetic account and reviewed journey recipes.
  Existing installed hosts were not modified or exposed to the fixture capture.
- VLP-1971 separately tracks inline customer Markdown documentation in the Portal.
  This branch does not claim that parked integration is implemented.
- Console MCP get_capabilities, decision requests and development context each
  timed out. Authoritative CLI reads/writes worked; VLP-2169 tracks this branch.
- Anchor checks and dependency matching do not prove arbitrary source semantics.
  Unclassified changes and deployment overrides are review items, not published claims.
