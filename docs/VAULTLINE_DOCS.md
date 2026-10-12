# Vaultline Docs pipeline

## Run the complete demonstration

From this checkout, after the README setup:

```bash
.venv/bin/python -m vaultline_docs demo
```

The command creates a temporary Git repository from `examples/fixture/`, commits
its initial application and support contracts, serves each variant on its own
loopback port, and opens fresh isolated Chromium contexts. The built-in synthetic
test account is `docs-reviewer`; it has no password, production account or reused
browser session. The media is the generated illustration in `media.svg`.

The command exports a baseline, changes the application's actual search label
through its source support contract, commits that change, and exports a second
package against the baseline. It asserts that only the search guide is marked
affected, its screenshot changes, both client notes survive, all input manifests
remain byte-identical, and disabled download/interruption guides and images are
absent. Downloaded fixture bytes are checked against the source hash. Test servers
and temporary product Git repositories are removed on exit.

Studio enables Core, Archive and Relay, with remoteTransfer true. Archive Only
enables Core and Archive, with remoteTransfer false. The guide filter requires
both selected modules and explicit feature/capability values. Remote download is
an Archive feature in actual Media Nexus; adding Relay does not enable it by itself.

## Generate Media Nexus source-supported drafts

The checked sample uses this exact remote Core revision, declaring version 1.0.157:

```bash
.venv/bin/python -m vaultline_docs generate \
  --repo ../core \
  --revision 282cf8585973c6dcaa2bd5c99d113300886656ec \
  --recipes examples/media-nexus-recipes.json \
  --manifest examples/deployments/nexus-studio.json \
  --manifest examples/deployments/nexus-archive-only.json \
  --source-only \
  --output output/media-nexus
```

These are synthetic configuration examples, not actual client definitions or
installed-host evidence. They contain the requested search/collection, download,
and interruption guides, with unsupported capabilities omitted. Screenshot status
is `not-captured`, and runtime review is an explicit review item. Source inspection
reads committed files through `git show`; it never silently reads concurrent dirty
Core edits. Declared deployment versions must match the source product version.
For a newer Core revision, review the recipe anchors and update the synthetic
manifest's version from `product/product.json`. Missing anchors withhold the guide.

## Supply another repository or code change

```bash
.venv/bin/python -m vaultline_docs generate \
  --repo /path/to/product-repository --revision EXACT_COMMIT --since PRIOR_COMMIT \
  --recipes reviewed-recipes.json \
  --manifest synthetic-deployment.json \
  --test-url studio=http://127.0.0.1:PORT \
  --previous /path/to/prior-package --output output/packages
```

The path examples are arguments, not values stored in customer guides. Recipes
identify guides, dependency paths, prerequisites, steps, expected results, recovery
and review notes. Two source modes are available:

- `contract`: a repository-owned JSON support contract containing those fields.
  A running test application uses the same exact contract revision. The included
  fixture demonstrates this mode; each source step has locator actions and expected
  result assertions.
- `evidence`: reviewed instructions bound to exact source anchors, file hashes and
  line references, as in the Media Nexus recipe. Missing evidence withholds a guide.
  A future behavior change that keeps an anchor intact can still need editorial
  review; anchor presence is evidence location, not semantic proof. Changed source
  dependencies identify affected guides; unclassified changed paths become explicit
  review items. The pipeline does not claim to understand arbitrary code or PRDs.

Capture requires an adapter-provided `GET /__vaultline_docs` identity on a synthetic
loopback test deployment. This is a **test adapter contract**, not an invented Media
Nexus or Portal API. It returns exactly: `synthetic: true`, `test_account:
docs-reviewer`, `source_revision`, `version`, `modules`, `platform`, `config_sha256`,
and `contracts` mapping support-contract paths to hashes. See `fixture.py` for the
executable example. For a real Core test deployment, a reviewed test adapter must
bind its actual source/config identity and synthetic account to equivalent journeys;
that integration is not installed in this PR. Without it, use `--source-only`.

For full capture each step supplies `actions` (`click`, `fill`, `check`, `download`)
and `assertions` using selectors and expected text. A download action requires its
expected SHA-256. Network assets are restricted to the exact loopback origin;
production cookies/storage are never reused. Assertions run before screenshots.
Visible text and input values are checked for credentials and sensitive paths.
Those checks are defence in depth; review all fixture inputs and screenshots.
No customer media, test account credentials or private deployment facts belong in
the public fork. Keep real private manifests outside this checkout and protect their
local export packages appropriately. Secret manifest fields are rejected.

## Shared guides and deployment overrides

Manifests contain id, label, product, version, platform, modules, config, synthetic,
and overrides. Guide gates require explicit config values; absent flags are false.
Overrides are keyed by stable guide id and the sections `prerequisites`, `steps`,
`expected`, `recovery`, `notes`. They are additive Markdown instructions, rendered
under Deployment instruction or Deployment notes. They cannot replace base text.
Unknown guide ids, section names, module ids and manifest fields are rejected.

Generation reads manifests but never writes them. Each package saves the manifest
and its hash. Changing the base cannot delete an intentional deployment instruction.
Overrides for an unavailable feature are preserved in the input and excluded from
that deployment's exported guide. They reappear if the feature is later enabled.
Human-authored overrides are listed for review: base screenshot assertions do not
verify extra client steps. Conflicting or stale instructions need human resolution.

## Review and Portal import

Open `deployments/DEPLOYMENT/index.html`, compare `documentation.diff`, inspect
`review.json` and `capture-evidence.json`, and review draft `release-notes.md`.
Metadata records the exact source revision, declared product/deployment version,
platform, selected modules, generation timestamp, manifest hash and capture status.
Every run creates a new versioned directory; failure removes the staging directory
and never overwrites the prior package. Archives and checksums support transport.

The filesystem adapter exports individual self-contained PDF attachments no larger
than the Portal's 25 MiB limit, with titles, dates, scope, size and hashes in
`package.json`. After explicit publication authorization, an administrator can use
the existing Portal Documents form to attach them to the appropriate organization.
The form uses signed upload intents and server-verified document creation. No
adapter here calls that interface, supplies tenant ids, emails clients, or replaces
an existing document. Never treat the export manifest as an API request body.
Markdown remains useful as editable source; uploading a Markdown file alone cannot
resolve sibling screenshot paths in the current Portal. Use the embedded-image PDF.

## Verification and licensing

```bash
.venv/bin/python -m unittest discover -s tests -v
```

Tests exercise the full pipeline, immutable source reads, missing evidence,
unknown changed paths, capability filtering, override preservation, failed running
identity, external-origin denial, credential/path rejection, package checksums,
PDF draft metadata and downloaded media bytes. Optional visual QA uses Poppler:

```bash
pdftoppm -png path/to/guide.pdf output/qa/guide
```

Exports include unchanged upstream LICENSE, full COPYING, derivative NOTICE and
`generator-source.zip`, an allowlisted corresponding source snapshot with file
hashes. It excludes private product repositories, private manifests, credentials,
runtime state and customer data. The snapshot includes the generator, upstream
utilities/skills, build/dependency instructions, synthetic fixture and tests.
The GPL grant is version 3 or later; preserve attribution and applicable source
delivery obligations when distributing the modified software. Generated guides
are marked as drafts and retain the package attribution.
