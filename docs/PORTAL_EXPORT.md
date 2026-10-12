# Native Portal integration

Generate as usual, then export the selected variant for its exact Portal tenant
and system identifiers:

```bash
python -m vaultline_docs generate \
  --repo /path/to/core --revision EXACT_CORE_COMMIT --since PREVIOUS_CORE_COMMIT \
  --recipes examples/media-nexus-recipes.json --manifest /private/deployment.json \
  --source-only --output output/packages
python -m vaultline_docs portal-export \
  --package output/packages/PACKAGE_ID --deployment DEPLOYMENT_ID \
  --organization-id PORTAL_ORGANIZATION_ID --system-id PORTAL_SYSTEM_ID \
  --output output/client.portal.json
```

Use a reviewed synthetic deployment/test adapter instead of --source-only when
actual-product screenshots can be captured. Source-only guides disclose missing
screenshots; do not mistake the fixture demonstration for installed Media Nexus proof.

In the existing Portal administrator client dashboard, choose the matching system
and import the JSON. The Portal validates the bound client/system, recorded version,
modules, guide capabilities, metadata, content limits and screenshot hashes. It
creates an immutable private draft. Compare with the published version, review the
configuration and preserved overrides, then explicitly publish. The client reads
and searches the guides natively and can download the complete Markdown/image set.
Publication and messaging are not performed by this command.

Export verifies every file checksum and retains separate shared base Markdown,
resolved deployment Markdown, override sections, capability requirements, generation
date, source revision, deployment version, configuration manifest hash, review items,
screenshots and attribution. It does not include private product repositories,
credentials, provider sessions, or an executable generator. It never writes to the
Portal, calls a publication endpoint, or stores a Portal password/session.

Packages generated before the capability catalogue was added must be regenerated;
export fails with an explicit message instead of assuming guide gates. Existing
exports are not overwritten. The native Portal limit is a complete package of up to
30 guides / 3.2 MB JSON with 800 KB per PNG; reduce screenshot sizes/count as needed.
One complete package is active per system, so independent partial packages do not
accumulate into a larger client library.

Real client manifests and generated client packages belong in private storage outside
the public fork. Only explicitly synthetic examples are committed. Keep GPL notices,
full license text and applicable corresponding-source obligations for software
distribution. The independent Portal reader consumes a data contract; no upstream
generator code is embedded into the Portal application.
