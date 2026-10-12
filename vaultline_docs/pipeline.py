"""Preview-only pipeline. No knowledge-base, portal write, or messaging clients."""
import difflib
import json
import shutil
import tempfile
import zipfile
import html
import os
from datetime import datetime, timezone
from pathlib import Path
from .source import Source, digest, load_guides, validate_manifest, safe_path
from .render import write_guide, pdf, CSS
from .capture import capture

ROOT = Path(__file__).resolve().parent.parent


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n')


def eligible(guide, manifest):
    if not set(guide.get('modules', [])) <= set(manifest['modules']):
        return False
    config = manifest.get('config', {})
    # Explicit capability values; never assume a missing flag is true.
    return all(config.get(key) == value for key,value in guide.get('requires', {}).items())


def review_diff(current, previous):
    before = {} if previous is None else {str(p.relative_to(previous)): p.read_text() for p in previous.rglob('*.md') if 'source' not in p.parts}
    after = {str(p.relative_to(current)): p.read_text() for p in current.rglob('*.md')}
    chunks = []
    for key in sorted(before.keys() | after.keys()):
        chunks.extend(difflib.unified_diff(before.get(key, '').splitlines(True), after.get(key, '').splitlines(True),
                                           fromfile='previous/' + key, tofile='current/' + key))
    return ''.join(chunks)


def source_bundle(destination):
    """Corresponding generator source, excluding secrets, private inputs and runtime state."""
    source = Source(ROOT)
    paths = source.git('ls-tree', '-r', '--name-only', source.revision).splitlines()
    allowed = ('vaultline_docs/', 'scripts/', 'utils/', '.claude/skills/', 'docs/', 'tests/', 'examples/fixture/')
    selected = {p for p in paths if p.startswith(allowed) or p in {'README.md', 'LICENSE', 'COPYING', 'NOTICE', 'requirements.txt', 'requirements-vaultline.txt', 'requirements-dev.txt', 'config.example.yaml', '.env.example', 'AGENTS.md'}}
    for folder in ('vaultline_docs', 'tests', 'examples/fixture'):
        selected.update(str(p.relative_to(ROOT)) for p in (ROOT / folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    selected.update(str(p.relative_to(ROOT)) for p in (ROOT / 'examples').glob('*.json'))
    selected.update(str(p.relative_to(ROOT)) for p in (ROOT / 'examples/deployments').glob('*.json'))
    selected.update({'COPYING', 'NOTICE', 'requirements-vaultline.txt', 'requirements-dev.txt', 'AGENTS.md'})
    with zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED) as archive:
        hashes = {}
        for name in sorted(selected):
            path = ROOT / name
            if path.exists() and not path.is_symlink():
                archive.write(path, name)
                hashes[name] = digest(path.read_bytes())
        archive.writestr('SOURCE-SNAPSHOT.json', json.dumps({'git_revision': source.revision, 'files': hashes}, indent=2))
    return digest(hashes)


def generate(repo, revision, recipes_path, manifest_paths, output, since=None, previous=None, urls=None, source_only=False):
    source = Source(repo, revision)
    recipes = json.loads(Path(recipes_path).read_text())
    guides, blocked, bindings = load_guides(source, recipes)
    ids = [spec['id'] for spec in recipes['guides']]
    manifests = [validate_manifest(json.loads(Path(p).read_text()), recipes['modules'], ids) for p in manifest_paths]
    if len({m['id'] for m in manifests}) != len(manifests):
        raise ValueError('Duplicate deployment id')
    if not manifests:
        raise ValueError('At least one deployment manifest is required')
    source_version = None
    if recipes.get('version_file'):
        source_version = json.loads(source.read(recipes['version_file']))[recipes['version_key']]
        if any(m['version'] != source_version for m in manifests):
            raise ValueError('Deployment version differs from source version; generate against the matching product revision')
    changed = source.changed(since) if since else []
    owned = {p for guide in guides for p in guide['dependencies']}
    unknown = sorted(set(changed) - owned)
    affected = [g['id'] for g in guides if not since or set(changed) & set(g['dependencies'])]
    now = datetime.now(timezone.utc).isoformat(timespec='microseconds')
    key = source.revision[:12] + '-' + digest({'manifests': manifests, 'recipes': recipes, 'time': now})[:12]
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    final = output / key
    previous = Path(previous).resolve() if previous else None
    if previous and not (previous / 'package.json').is_file():
        raise ValueError('Previous package is missing package.json')
    urls = urls or {}
    with tempfile.TemporaryDirectory(prefix='.docs-', dir=output) as temporary:
        package = Path(temporary)
        metadata = {'product': recipes['product'], 'source_revision': source.revision, 'generated_at': now, 'status': 'draft', 'package_id': key}
        if source_version:
            metadata['source_product_version'] = source_version
        for guide in guides:
            write_guide(package / 'base', guide, metadata)
        content = {g['id']: {k: g.get(k) for k in ('title', 'summary', 'prerequisites', 'steps', 'expected', 'recovery')} for g in guides}
        write_json(package / 'base/guide-content.json', content)
        old_content = json.loads((previous / 'base/guide-content.json').read_text()) if previous and (previous / 'base/guide-content.json').exists() else {}
        guide_changes = [{'guide': name, 'before': old_content.get(name), 'after': content.get(name)}
                         for name in sorted(content.keys() | old_content.keys()) if old_content.get(name) != content.get(name)]
        deployments = []
        capture_changes = []
        for manifest in manifests:
            destination = package / 'deployments' / manifest['id']
            destination.mkdir(parents=True)
            screenshot_dir = destination / 'screenshots'
            screenshot_dir.mkdir()
            included = [g for g in guides if eligible(g, manifest)]
            excluded = [spec['id'] for spec in recipes['guides'] if spec['id'] not in [g['id'] for g in included]]
            evidence = None
            if included and not source_only:
                if manifest['id'] not in urls:
                    raise ValueError('Missing synthetic test deployment URL for ' + manifest['id'])
                evidence = capture(urls[manifest['id']], manifest, source.revision, bindings, included, screenshot_dir)
                write_json(destination / 'capture-evidence.json', evidence)
                for name in screenshot_dir.glob('*.png'):
                    old = previous / 'deployments' / manifest['id'] / 'screenshots' / name.name if previous else None
                    capture_changes.append({'deployment': manifest['id'], 'file': name.name,
                                            'previous_sha256': digest(old.read_bytes()) if old and old.exists() else None,
                                            'sha256': digest(name.read_bytes())})
            deployment_metadata = {**metadata, 'product': manifest['product'], 'deployment': manifest['id'],
                                   'deployment_version': manifest['version'], 'platform': manifest['platform'],
                                   'modules': ', '.join(manifest['modules']), 'manifest_sha256': digest(manifest),
                                   'capture_status': 'verified-synthetic' if evidence else 'not-captured'}
            attachments = []
            for guide in included:
                records = evidence['guides'][guide['id']] if evidence else None
                body = write_guide(destination, guide, deployment_metadata, manifest, records)
                pdf(destination, guide, deployment_metadata, body)
                file = destination / (guide['id'] + '.pdf')
                if file.stat().st_size > 26_214_400:
                    raise ValueError('Portal PDF attachment exceeds its 25 MiB limit')
                attachments.append({'title': guide['title'], 'type': 'Guide', 'category': 'Resource',
                                    'scope': manifest['id'], 'date': now[:10], 'file': str(file.relative_to(package)),
                                    'content_type': 'application/pdf', 'size_bytes': file.stat().st_size,
                                    'sha256': digest(file.read_bytes()), 'state': 'draft'})
            index_links = '\n'.join('- [' + g['title'] + '](' + g['id'] + '.html)' for g in included)
            (destination / 'index.html').write_text('<!doctype html><meta charset="utf-8"><style>' + CSS + '</style><main><h1>Vaultline Docs - Draft</h1>' + __import__('markdown').markdown(index_links) + '</main>')
            # Preserve inputs byte-for-byte; generation never writes to manifests.
            write_json(destination / 'deployment.json', manifest)
            deployments.append({'id': manifest['id'], 'version': manifest['version'], 'manifest_sha256': digest(manifest),
                                'included': [g['id'] for g in included], 'excluded': excluded, 'attachments': attachments})
        for name in ('LICENSE', 'COPYING', 'NOTICE'):
            shutil.copyfile(ROOT / name, package / name)
        if recipes.get('synthetic_fixture') is True:
            with zipfile.ZipFile(package / 'test-product-source.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
                for path in sorted(owned):
                    archive.writestr(safe_path(path), source.read(path))
                archive.writestr('SOURCE-REVISION.txt', source.revision + '\n')
        snapshot = source_bundle(package / 'generator-source.zip')
        report = {'source_revision': source.revision, 'since': Source(repo, since).revision if since else None,
                  'changed_paths': changed, 'affected_guides': affected, 'unclassified_changes': unknown,
                  'blocked_guides': blocked, 'screenshot_changes': capture_changes,
                  'guide_changes': guide_changes,
                  'review_required': blocked + [{'reason': 'unclassified source change', 'path': p} for p in unknown]}
        for manifest in manifests:
            for name, sections in manifest.get('overrides', {}).items():
                if name in next(d for d in deployments if d['id'] == manifest['id'])['included']:
                    report['review_required'].append({'reason': 'Deployment override is preserved human-authored content; base journey assertions do not verify it.',
                                                      'deployment': manifest['id'], 'guide': name, 'sections': sorted(sections)})
        if source_only:
            report['review_required'].append({'reason': 'No running synthetic Media Nexus capture; source-supported instructions require runtime review.'})
        write_json(package / 'review.json', report)
        notes = []
        for change in guide_changes:
            if not change['after']:
                notes.append('- Withheld guide: ' + change['guide'] + '. Review missing source evidence before reuse.')
            elif not change['before']:
                notes.append('- Added draft guide: ' + change['after']['title'] + '.')
            else:
                notes.append('- Updated guide: ' + change['after']['title'] + '.')
                for old_step, new_step in zip(change['before']['steps'], change['after']['steps']):
                    if old_step['instruction'] != new_step['instruction']:
                        notes.append('  - Previous instruction: ' + old_step['instruction'])
                        notes.append('  - Current instruction: ' + new_step['instruction'])
        (package / 'release-notes.md').write_text('# Draft release notes\n\nSource revision: `' + source.revision + '`. Generated: ' + now + '.\n\nDocumentation updates:\n\n' + '\n'.join(notes or ['- No instructional changes; inspect affected source dependencies for editorial review.']) + '\n\nThese are documentation changes, not a claim that every source change is a released feature.\nReview review.json and documentation.diff before sending an announcement. No announcement has been sent.\n')
        panels = []
        previous_relative = os.path.relpath(previous, final) if previous else None
        for change in capture_changes:
            path = 'deployments/' + change['deployment'] + '/screenshots/' + change['file']
            panels.append('<h2>' + html.escape(change['deployment'] + ' / ' + change['file']) + '</h2><div style="display:flex;gap:12px">')
            if change['previous_sha256']:
                panels.append('<figure><figcaption>Previous</figcaption><img src="' + html.escape(previous_relative + '/' + path, quote=True) + '"></figure>')
            panels.append('<figure><figcaption>Current</figcaption><img src="' + html.escape(path, quote=True) + '"></figure></div>')
        (package / 'screenshot-review.html').write_text('<!doctype html><meta charset="utf-8"><style>' + CSS + 'figure{margin:0;flex:1}</style><main><h1>Screenshot review - Draft</h1>' + ''.join(panels) + '</main>')
        (package / 'SOURCE.md').write_text('# Corresponding source\n\nVaultline Docs derives from max-doc-AI under GPL-3.0-or-later. Original notices are preserved.\nThe complete generator source used for this draft is included in generator-source.zip,\nwith its revision and file hashes in SOURCE-SNAPSHOT.json.\nFork: https://github.com/jake-vaultline/vaultline-docs\n\nProduct repositories inspected by the generator are inputs, not part of this source archive.\nBefore distributing executable derivatives, retain the applicable GPL notices, license and\nCorresponding Source delivery obligations. A docs export is not authorization to distribute\nprivate product source, deploy software, publish Support content or contact customers.\n')
        package_data = {**metadata, 'schema_version': 1, 'generator_source_sha256': snapshot,
                        'mode': 'filesystem-preview', 'publication': 'not-authorized',
                        'deployments': deployments, 'blocked_guides': blocked,
                        'portal': {'adapter': 'filesystem', 'max_attachment_bytes': 26_214_400,
                                   'state': 'administrator-upload-not-run',
                                   'interface': 'POST /api/admin/documents/upload-intent; signed upload PUT; POST /api/admin/documents',
                                   'blocker': 'No authorized authenticated Portal administrator upload session. Support is contact guidance; inline Markdown help-center work is separately tracked.'}}
        write_json(package / 'package.json', package_data)
        (package / 'portal-import.md').write_text('# Portal import preview\n\nNo live writes occurred. Use the existing Portal administrator Documents form after approval.\nChoose the client organization and a Resource document, attach the listed PDF, then save.\nThe Portal obtains a signed upload intent, uploads bytes, and saves the document only after\nvalidating its organization, file size and content type. Never submit package.json as a Portal API payload.\nPDFs embed screenshots; uploading individual Markdown attachments does not resolve sibling image paths.\nHTML and ZIP are local previews/archives; the Portal does not accept them as attachments.\n\nReview package.json for each attachment path, size, SHA-256 and deployment. Live tenant ids\nand upload ids are intentionally absent; the authenticated Portal generates them.\n')
        (package / 'documentation.diff').write_text(review_diff(package, previous))
        write_json(package / 'checksums.json', {str(p.relative_to(package)): digest(p.read_bytes()) for p in package.rglob('*') if p.is_file()})
        package.rename(final)
    # An archive for local transport; Portal consumes individual PDFs, not this archive.
    shutil.make_archive(str(final), 'zip', final)
    return final
