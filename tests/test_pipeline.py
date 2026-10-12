import json
import tempfile
import unittest
from pathlib import Path
from vaultline_docs.__main__ import commit, demo
from vaultline_docs.source import Source, safe_path, slug, check_text, load_guides, validate_manifest
from vaultline_docs.pipeline import generate, ROOT, eligible
from vaultline_docs.capture import origin, capture
from vaultline_docs.fixture import serve
import subprocess


class ContractTests(unittest.TestCase):
    def test_reject_sensitive_content_and_traversal(self):
        for text in ('Bearer abcdef', '/Users/private/media', 'password=real-value', 'sk-ant-example', '{"api_key": "real-value"}', '{"password": "real-value"}'):
            with self.assertRaises(ValueError):
                check_text(text)
        for path in ('../outside', '/absolute', '.env', 'nested/.secret', 'a\\b'):
            with self.assertRaises(ValueError):
                safe_path(path)
        with self.assertRaises(ValueError):
            slug('../../client')

    def test_capture_cannot_use_external_origins(self):
        for url in ('https://production.example', 'http://127.0.0.1:90/?token=secret', 'http://name:secret@localhost:90', 'http://127.0.0.1.evil.example'):
            with self.assertRaises(ValueError):
                origin(url)

    def test_capabilities_are_explicit_and_independent_of_relay(self):
        guide = {'modules': ['archive'], 'requires': {'remoteTransfer': True}}
        self.assertFalse(eligible(guide, {'modules': ['archive', 'relay'], 'config': {}}))
        self.assertFalse(eligible(guide, {'modules': ['archive', 'relay'], 'config': {'remoteTransfer': False}}))
        self.assertTrue(eligible(guide, {'modules': ['archive'], 'config': {'remoteTransfer': True}}))

    def test_unknown_override_and_manifest_fields_are_rejected(self):
        manifest = json.loads((ROOT / 'examples/deployments/studio.json').read_text())
        manifest['overrides']['unknown-guide'] = {'notes': 'Unsupported'}
        with self.assertRaises(ValueError):
            validate_manifest(manifest, ['core', 'archive', 'relay'], ['search-collection'])
        del manifest['overrides']['unknown-guide']
        manifest['customer_password'] = 'must not be stored'
        with self.assertRaises(ValueError):
            validate_manifest(manifest, ['core', 'archive', 'relay'], ['search-collection'])

    def test_source_inspection_is_revision_pinned_and_missing_anchor_withholds(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp)
            subprocess.run(['git', 'init', '-q', str(repo)], check=True)
            (repo / 'app.py').write_text('Search archive\n')
            revision = commit(repo, 'Source fixture')
            (repo / 'app.py').write_text('Uncommitted planned feature\n')
            source = Source(repo, revision)
            self.assertEqual(source.read('app.py'), 'Search archive\n')
            recipes = {'guides': [{'id': 'search', 'evidence': [{'path': 'app.py', 'anchor': 'planned feature'}]}]}
            guides, blocked, _ = load_guides(source, recipes)
            self.assertEqual(guides, [])
            self.assertEqual(blocked[0]['guide'], 'search')

    def test_wrong_running_identity_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp) / 'repo'
            __import__('shutil').copytree(ROOT / 'examples/fixture', repo)
            subprocess.run(['git', 'init', '-q', str(repo)], check=True)
            revision = commit(repo, 'Fixture')
            source = Source(repo, revision)
            recipes = json.loads((ROOT / 'examples/fixture-recipes.json').read_text())
            guides, _, bindings = load_guides(source, recipes)
            manifest = json.loads((ROOT / 'examples/deployments/studio.json').read_text())
            with serve(source, recipes, manifest, bindings) as url:
                wrong = {**manifest, 'version': 'different-deployment'}
                with self.assertRaisesRegex(ValueError, 'identity'):
                    capture(url, wrong, revision, bindings, guides, Path(temp))

    def test_source_only_reports_unclassified_changes_and_missing_runtime(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = root / 'repo'
            __import__('shutil').copytree(ROOT / 'examples/fixture', repo)
            subprocess.run(['git', 'init', '-q', str(repo)], check=True)
            old = commit(repo, 'Fixture')
            (repo / 'unmapped.py').write_text('unsupported_feature = True\n')
            new = commit(repo, 'Unknown feature')
            package = generate(repo, new, ROOT / 'examples/fixture-recipes.json', [ROOT / 'examples/deployments/studio.json'], root / 'out', old, source_only=True)
            report = json.loads((package / 'review.json').read_text())
            self.assertEqual(report['unclassified_changes'], ['unmapped.py'])
            self.assertTrue(any('No running' in r['reason'] for r in report['review_required']))
            self.assertFalse(list(package.rglob('*.png')))
            with __import__('zipfile').ZipFile(package / 'generator-source.zip') as archive:
                self.assertIn('examples/fixture/app.html', archive.namelist())
                self.assertIn('COPYING', archive.namelist())


class EndToEndTests(unittest.TestCase):
    def test_complete_pipeline_and_override_preservation(self):
        with tempfile.TemporaryDirectory() as temp:
            result = demo(temp)
            package = Path(result['updated'])
            for path in package.rglob('*.pdf'):
                from pypdf import PdfReader
                reader = PdfReader(path)
                self.assertTrue(reader.pages)
                self.assertIn('DRAFT', reader.pages[0].extract_text())
            hashes = json.loads((package / 'checksums.json').read_text())
            from vaultline_docs.source import digest
            for name, hash in hashes.items():
                self.assertEqual(digest((package / name).read_bytes()), hash)
            package_data = json.loads((package / 'package.json').read_text())
            self.assertEqual(package_data['publication'], 'not-authorized')
            studio = next(d for d in package_data['deployments'] if d['id'] == 'studio')
            archive = next(d for d in package_data['deployments'] if d['id'] == 'archive-only')
            self.assertEqual(len(studio['included']), 3)
            self.assertEqual(archive['included'], ['search-collection'])
            evidence = json.loads((package / 'deployments/studio/capture-evidence.json').read_text())
            self.assertEqual(len(evidence['guides']['download-media'][1]['downloads']), 1)
            self.assertIn('Previous instruction:', (package / 'release-notes.md').read_text())
            self.assertTrue((package / 'test-product-source.zip').exists())


if __name__ == '__main__':
    unittest.main()
