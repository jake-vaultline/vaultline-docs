"""Bounded, revision-pinned source inspection. Never read the dirty working tree."""
import hashlib
import json
import re
import subprocess
from pathlib import PurePosixPath


def digest(value):
    if not isinstance(value, bytes):
        value = json.dumps(value, sort_keys=True).encode()
    return hashlib.sha256(value).hexdigest()


def safe_path(value):
    p = PurePosixPath(value)
    if p.is_absolute() or '..' in p.parts or not p.parts or '\\' in value:
        raise ValueError('Expected a repository-relative path')
    if any(part.startswith('.') for part in p.parts):
        raise ValueError('Hidden paths are not documentation inputs')
    return str(p)


def slug(value):
    if not isinstance(value, str) or not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,79}', value):
        raise ValueError('Expected a lowercase, bounded identifier')
    return value


def check_text(text):
    # Defence in depth, not a substitute for synthetic input review.
    if re.search(r'(?:gh[pousr]_|sk-ant-|sk_live_|Bearer\s+\S+|(?:password|token|secret|api[_-]?key)["\']?\s*[:=]\s*\S+|/Users/|/Volumes/|/home/)', text, re.I):
        raise ValueError('Potential credential or sensitive path in documentation')
    return text


class Source:
    def __init__(self, repo, revision='HEAD'):
        self.repo = repo
        self.revision = self.git('rev-parse', '--verify', revision + '^{commit}').strip()

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.repo), *args], text=True, stderr=subprocess.PIPE)

    def read(self, path):
        path = safe_path(path)
        # git show refuses a missing file; no fallback to unrelated local material.
        text = self.git('show', self.revision + ':' + path)
        if len(text.encode()) > 2_000_000:
            raise ValueError('Source file exceeds bounded inspection size')
        return text

    def changed(self, since):
        old = Source(self.repo, since).revision
        return self.git('diff', '--name-only', old, self.revision, '--').splitlines()

    def evidence(self, item):
        text = self.read(item['path'])
        anchor = item['anchor']
        if anchor not in text:
            raise ValueError('Source anchor missing: ' + item['path'])
        return {'path': item['path'], 'line': text[:text.index(anchor)].count('\n') + 1,
                'sha256': digest(text.encode()), 'anchor_sha256': digest(anchor.encode())}


def load_guides(source, recipes):
    """Recipes are reviewed mappings, not an assertion that any code is understood."""
    guides, blocked, bindings = [], [], {}
    for spec in recipes['guides']:
        identifier = slug(spec['id'])
        try:
            if 'contract' in spec:
                contract = safe_path(spec['contract'])
                guide = json.loads(source.read(contract))
                bindings[contract] = digest(source.read(contract).encode())
                guide['dependencies'] = [contract] + spec.get('dependencies', [])
                # Structured support contracts carry the source-authored steps;
                # every step's runtime selectors are verified during capture.
                evidence = [{'path': contract, 'line': 1, 'sha256': bindings[contract]}]
            else:
                guide = dict(spec)
                evidence = [source.evidence(e) for e in spec['evidence']]
                guide['dependencies'] = [e['path'] for e in evidence] + spec.get('dependencies', [])
            if guide['id'] != identifier:
                raise ValueError('Guide id differs from recipe')
            if not evidence or not guide.get('steps') or not guide.get('prerequisites') or not guide.get('expected'):
                raise ValueError('Guide lacks evidence, prerequisites, steps or expected result')
            check_text(json.dumps(guide))
            guide['evidence'] = evidence
            guides.append(guide)
        except (ValueError, KeyError, subprocess.CalledProcessError, json.JSONDecodeError) as error:
            # Do not echo source, input credentials, or subprocess stderr.
            blocked.append({'guide': identifier, 'reason': type(error).__name__,
                            'resolution': 'Review the recipe and exact source anchors at this revision.'})
    return guides, blocked, bindings


def validate_manifest(manifest, known_modules, guide_ids):
    allowed = {'id', 'label', 'product', 'version', 'platform', 'modules', 'config', 'overrides', 'synthetic'}
    if set(manifest) - allowed:
        raise ValueError('Unknown manifest fields')
    slug(manifest['id'])
    if not isinstance(manifest.get('modules'), list) or any(not isinstance(m, str) for m in manifest['modules']):
        raise ValueError('Deployment modules must be a list of module ids')
    if not isinstance(manifest.get('config', {}), dict) or not isinstance(manifest.get('overrides', {}), dict):
        raise ValueError('Deployment config and overrides must be objects')
    if 'synthetic' in manifest and not isinstance(manifest['synthetic'], bool):
        raise ValueError('Synthetic marker must be a boolean')
    for key in ('label', 'product', 'version', 'platform'):
        if not isinstance(manifest[key], str) or not manifest[key].strip():
            raise ValueError('Missing manifest ' + key)
    if len(set(manifest['modules'])) != len(manifest['modules']) or set(manifest['modules']) - set(known_modules):
        raise ValueError('Unknown or duplicate deployment modules')
    check_text(json.dumps(manifest))
    for identifier, sections in manifest.get('overrides', {}).items():
        if identifier not in guide_ids or set(sections) - {'prerequisites', 'steps', 'expected', 'recovery', 'notes'}:
            raise ValueError('Override refers to unknown guide or section')
        # Additive overrides cannot replace or silently erase shared steps.
        if any(not isinstance(text, str) or not text.strip() for text in sections.values()):
            raise ValueError('Overrides must be nonempty Markdown strings')
    return manifest
