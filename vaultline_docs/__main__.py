"""Run with python -m vaultline_docs demo or generate --help."""
import argparse
import json
import shutil
import subprocess
import tempfile
from contextlib import ExitStack
from pathlib import Path
from .source import Source, load_guides, digest
from .fixture import serve
from .pipeline import generate, ROOT, write_json


def commit(repo, message):
    subprocess.run(['git', '-C', str(repo), 'add', '.'], check=True, stdout=subprocess.DEVNULL)
    subprocess.run(['git', '-C', str(repo), '-c', 'user.name=Vaultline Docs Fixture', '-c', 'user.email=docs@example.invalid', 'commit', '-qm', message], check=True)
    return Source(repo).revision


def fixture_package(repo, revision, manifests, output, since=None, previous=None):
    recipes_path = ROOT / 'examples/fixture-recipes.json'
    recipes = json.loads(recipes_path.read_text())
    source = Source(repo, revision)
    guides, blocked, bindings = load_guides(source, recipes)
    if blocked:
        raise ValueError('Fixture contracts are invalid')
    with ExitStack() as stack:
        urls = {}
        for path in manifests:
            manifest = json.loads(Path(path).read_text())
            urls[manifest['id']] = stack.enter_context(serve(source, recipes, manifest, bindings))
        return generate(repo, revision, recipes_path, manifests, output, since, previous, urls)


def demo(output):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='vaultline-docs-fixture-') as temp:
        repo = Path(temp) / 'product'
        shutil.copytree(ROOT / 'examples/fixture', repo)
        subprocess.run(['git', 'init', '-q', str(repo)], check=True)
        old = commit(repo, 'Initial synthetic archive with search, collections and downloads')
        manifests = []
        for name in ('studio', 'archive-only'):
            target = Path(temp) / (name + '.json')
            shutil.copyfile(ROOT / 'examples/deployments' / (name + '.json'), target)
            manifests.append(target)
        baseline = fixture_package(repo, old, manifests, output)
        # Representative source change: actual rendered label and its exact steps change.
        contract = repo / 'search-collection.json'
        contract.write_text(contract.read_text().replace('Search archive', 'Search media'))
        new = commit(repo, 'Rename source-supported search control to Search media')
        before_hashes = {p.name: digest(p.read_bytes()) for p in manifests}
        updated = fixture_package(repo, new, manifests, output, since=old, previous=baseline)
        report = json.loads((updated / 'review.json').read_text())
        assert report['affected_guides'] == ['search-collection'], report
        assert not report['unclassified_changes']
        for path in manifests:
            assert digest(path.read_bytes()) == before_hashes[path.name], 'Manifest was modified'
            manifest = json.loads(path.read_text())
            guide = (updated / 'deployments' / manifest['id'] / 'search-collection.md').read_text()
            assert manifest['overrides']['search-collection']['notes'] in guide, 'Client override lost'
            assert 'Search media' in guide and 'Search archive and click' not in guide
        archive = updated / 'deployments/archive-only'
        assert not (archive / 'download-media.md').exists()
        assert not (archive / 'interrupted-transfer.md').exists()
        assert not list((archive / 'screenshots').glob('download-*'))
        studio = updated / 'deployments/studio'
        assert (studio / 'download-media.pdf').exists()
        screenshot = next(x for x in report['screenshot_changes'] if x['deployment'] == 'studio' and x['file'] == 'search-collection-step-1.png')
        assert screenshot['sha256'] != screenshot['previous_sha256'], 'Screenshot did not refresh after source change'
        assert '+### 1. Search media' in (updated / 'documentation.diff').read_text()
        result = {'baseline': str(baseline), 'updated': str(updated), 'source_before': old, 'source_after': new,
                  'checks': ['source change -> relevant guide and screenshot', 'two capability-filtered deployments',
                             'overrides preserved and manifests unchanged', 'fresh screenshot step assertions',
                             'downloaded synthetic media bytes match source', 'reviewable diff and draft release notes',
                             'PDFs embed screenshots; no live publication or messages']}
        write_json(output / 'demo-result.json', result)
        print(json.dumps(result, indent=2))
        return result


def main():
    parser = argparse.ArgumentParser(description='Vaultline Docs: source-backed, deployment-aware draft packages')
    commands = parser.add_subparsers(dest='command', required=True)
    demo_parser = commands.add_parser('demo', help='Generate and verify two versions and two synthetic variants end to end')
    demo_parser.add_argument('--output', default='output/demo')
    gen = commands.add_parser('generate', help='Generate from an exact supplied repository revision and reviewed recipe')
    gen.add_argument('--repo', required=True)
    gen.add_argument('--revision', default='HEAD')
    gen.add_argument('--since')
    gen.add_argument('--recipes', required=True)
    gen.add_argument('--manifest', action='append', required=True)
    gen.add_argument('--output', default='output/packages')
    gen.add_argument('--previous')
    gen.add_argument('--test-url', action='append', default=[], help='DEPLOYMENT=http://127.0.0.1:PORT (identity-bound test adapter)')
    gen.add_argument('--source-only', action='store_true', help='Explicitly report missing screenshots and runtime verification')
    portal = commands.add_parser('portal-export', help='Export an immutable client/system-bound Portal import JSON; never publishes')
    portal.add_argument('--package',required=True)
    portal.add_argument('--deployment',required=True)
    portal.add_argument('--organization-id',required=True)
    portal.add_argument('--system-id',required=True)
    portal.add_argument('--output',required=True)
    args = parser.parse_args()
    try:
        if args.command == 'demo':
            demo(args.output)
        elif args.command == 'portal-export':
            from .portal import export
            print(export(args.package,args.deployment,args.organization_id,args.system_id,args.output))
        else:
            urls = dict(value.split('=', 1) for value in args.test_url)
            result = generate(args.repo, args.revision, args.recipes, args.manifest, args.output,
                              args.since, args.previous, urls, args.source_only)
            print(result)
    except (ValueError, subprocess.CalledProcessError, KeyError, json.JSONDecodeError) as error:
        parser.exit(1, 'Documentation generation withheld: ' + (str(error) if isinstance(error, ValueError) else type(error).__name__) + '\n')


if __name__ == '__main__':
    main()
