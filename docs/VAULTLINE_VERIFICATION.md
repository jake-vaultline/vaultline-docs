# Verification - 2026-10-12

Environment: macOS, Python 3.9.6, Playwright 1.60.0 / Chromium 148.0.7778.96.
Vaultline task: VLP-2169. No production/customer system was changed.

## Executed checks

- `python -m unittest discover -s tests -v`: 8 tests pass, including the complete
  two-version/two-deployment workflow, missing evidence, unknown source changes,
  source pinning despite dirty edits, identity mismatch, capability filtering,
  sensitive-content/path rejection, source archive contents and byte-verified download.
- `python -m vaultline_docs demo`: complete pass. The committed fixture's Search
  archive control changes to Search media; the affected guide list contains only
  search-collection, its source-backed instructions and screenshots change, and both
  preserved deployment-note strings remain in their output. Manifests are unchanged.
- Two variants: Studio has Core, Archive, Relay and remote downloads; Archive Only
  has Core, Archive and remote downloads disabled. Studio receives all three guides;
  Archive Only receives search/collection only. No download/interruption guide or
  image is emitted for Archive Only.
- Each run captures 11 fresh screenshots: 8 Studio step states and 3 Archive Only
  step states. Assertions precede each screenshot. Browser download bytes match the
  source fixture's SHA-256. The two-version demonstration performs 22 step captures.
- PDFs reopen with draft metadata; package file checksums verify. All attachments
  are below 25 MiB. Rendered PDF pages and screenshot contact sheets were visually
  inspected. Step text/images are grouped to avoid disconnected screenshots.
- HTML guide previews were checked for loaded images and horizontal overflow; see
  the final sample receipt for the measured count.
- `python -m vaultline_docs generate ... --source-only` against Core
  `282cf8585973c6dcaa2bd5c99d113300886656ec`: source-supported drafts for Media Nexus
  1.0.157. Runtime verification and screenshots are explicitly not captured; no
  fixture images are presented as real Media Nexus screenshots.
- `python -m compileall -q vaultline_docs scripts utils`, `git diff --check`: pass.
- Unchanged upstream ScreenshotCapturer successfully captured the synthetic fixture
  login in an isolated context with no auth session, config.yaml, AI or KB provider.
  Upstream discovery found 15 demo docs and Markdown structure validation passed.

## Evidence interpretation

The fixture exercises a real served application, synthetic login/session, archive
search, selected-media collection creation, download preparation, downloadable
media bytes, interruption and recovery. Its simplified Resume behavior does not
prove Media Nexus Prepare again, browser partial-save resumption, native drive copy,
source retention, installed-host commissioning or client acceptance.

The complete exported package contains `review.json`, `documentation.diff`,
`screenshot-review.html`, per-deployment `capture-evidence.json`, `checksums.json`,
versioned metadata, PDF/Markdown/HTML guides, corresponding source and draft notes.
Screenshots show only the synthetic test account and generated illustration.
No credentials, production cookies, client records or sensitive filesystem paths
are included in those screenshot journeys.

Upstream health is not green: 4 pass / 7 configuration/registration failures.
Paid Claude/Gemini workflows and Pylon/Zendesk writes are not run. There are no
upstream GitHub CI workflows, so local checks are the execution evidence here.
Portal upload/readback and real synthetic Media Nexus screenshot qualification are
remaining integration gates. Publication/customer messaging require authorization.
