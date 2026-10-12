# Vaultline Docs

Track Vaultline development through the workspace Console contract. Preserve
upstream notices and the upstream remote. Work on task branches.

The supported default is `python -m vaultline_docs demo`. It uses a disposable
synthetic fixture and writes versioned drafts under output/. Never use real client
data or credentials in the fixture. Never call upstream sync-docs/create-release
to publish a Vaultline package without explicit authorization.

Keep recipes (shared source-supported instructions) and manifest overrides
(deployment instructions) separate. Missing evidence must block the affected guide,
not invent a replacement. Generated files are disposable; edit inputs instead.

Verify with `python -m unittest discover -s tests -v` and the demo. No paid APIs,
external publication, customer messaging, or live Support edits are part of tests.
