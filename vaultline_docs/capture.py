"""Fresh isolated browser journeys on identity-bound synthetic loopback deployments."""
import json
import tempfile
from pathlib import Path
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright, expect
from .source import check_text, digest


def origin(url):
    p = urlparse(url)
    if p.scheme != 'http' or p.hostname not in ('127.0.0.1', 'localhost', '::1') or p.username or p.password or p.path not in ('', '/') or p.query or p.fragment:
        raise ValueError('Capture requires a plain loopback test origin')
    return url.rstrip('/')


def live_core_evidence(page, url):
    """Refuse a screenshot unless the rendered UI is backed by the live Core APIs."""
    me = page.request.get(url + '/api/me')
    bootstrap = page.request.get(url + '/api/bootstrap/v2')
    if not me.ok or me.json().get('authenticated') is not True:
        raise ValueError('Synthetic Core session is not authenticated')
    if not bootstrap.ok:
        raise ValueError('Live Core bootstrap is unavailable; static demo fallback refused')
    assets = bootstrap.json().get('assets', [])
    if not any(asset.get('id') == 'docs-ridge-sunrise' for asset in assets):
        raise ValueError('Live Core bootstrap does not contain the seeded synthetic asset')
    ui_live = page.evaluate("() => typeof API !== 'undefined' && API.live === true")
    if ui_live is not True:
        raise ValueError('Rendered Core UI is not in live mode; static demo fallback refused')
    return {'authenticated': True, 'asset_id': 'docs-ridge-sunrise', 'ui_mode': 'live-core'}


def persistence_evidence(page, url, contract, step):
    response = page.request.get(url + contract['path'])
    if not response.ok:
        raise ValueError('Synthetic Core persistence proof is unavailable')
    proof = response.json()
    if proof.get('ui_mode') != 'live-core':
        raise ValueError('Synthetic Core persistence proof did not come from live Core')
    if step < contract['after_step']:
        return proof
    expected = {
        'name': contract['collection'],
        'note': 'Synthetic documentation review only',
        'member_ids': [contract['asset_id']],
        'member_count': 1,
    }
    if proof.get('collection') != expected:
        raise ValueError('Saved Core collection does not contain the exact synthetic member')
    asset = proof.get('asset', {})
    if (asset.get('id') != contract['asset_id'] or
            asset.get('source_path_sha256') != contract['source_path_sha256'] or
            asset.get('source_path_unchanged') is not True):
        raise ValueError('Synthetic asset source locator changed during collection creation')
    return proof


def capture(url, manifest, revision, bindings, guides, output):
    url = origin(url)
    if manifest.get('synthetic') is not True:
        raise ValueError('Capture requires an explicitly synthetic deployment')
    results = {}
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context(viewport={'width': 1200, 'height': 840}, service_workers='block')
        # All network requests, including redirects/assets, are confined to this test origin.
        context.route('**/*', lambda route: route.continue_() if route.request.url.startswith(url + '/') else route.abort())
        page = context.new_page()
        page.set_default_timeout(8000)
        response = page.request.get(url + '/__vaultline_docs')
        if not response.ok:
            raise ValueError('Test deployment identity endpoint is unavailable')
        identity = response.json()
        expected_identity = {'source_revision': revision, 'version': manifest['version'],
                             'modules': manifest['modules'], 'platform': manifest['platform'],
                             'config_sha256': digest(manifest.get('config', {})),
                             'contracts': bindings, 'synthetic': True, 'test_account': 'docs-reviewer'}
        if {key: value for key, value in identity.items()
                if key not in {'capture_session', 'capture_proof'}} != expected_identity:
            raise ValueError('Test deployment identity does not match source/manifest')
        session = identity.get('capture_session')
        if session is not None:
            if session != {'mode': 'endpoint', 'method': 'GET', 'path': '/__vaultline_docs/session'}:
                raise ValueError('Unsupported synthetic capture session contract')
            started = page.request.get(url + session['path'])
            if not started.ok or started.json() != {'ok': True, 'test_account': 'docs-reviewer'}:
                raise ValueError('Synthetic capture session could not start')
        proof_contract = identity.get('capture_proof')
        if proof_contract != {'method': 'GET', 'path': '/__vaultline_docs/proof', 'after_step': 2,
                              'collection': 'ARCHIVE-DOCS-SELECTS',
                              'asset_id': 'docs-ridge-sunrise',
                              'source_path_sha256': digest(b'/synthetic/docs/Ridge Sunrise.mp4')}:
            raise ValueError('Unsupported synthetic persistence proof contract')
        for guide in guides:
            records = []
            page.goto(url + '/')
            if session is None:
                expect(page.get_by_role('button', name='Start synthetic session', exact=True)).to_be_visible()
                page.get_by_role('button', name='Start synthetic session', exact=True).click()
            for index, step in enumerate(guide['steps'], 1):
                downloads = []
                for action in step.get('actions', []):
                    target = page.locator(action['selector'])
                    operation = action['op']
                    if operation == 'click':
                        target.click()
                    elif operation == 'fill':
                        target.fill(action['value'])
                    elif operation == 'press':
                        target.press(action['key'])
                    elif operation == 'check':
                        target.check()
                    elif operation == 'download':
                        with page.expect_download() as pending:
                            target.click()
                        downloaded = pending.value
                        with tempfile.TemporaryDirectory() as temp:
                            file = Path(temp) / 'synthetic-download'
                            downloaded.save_as(str(file))
                            content = file.read_bytes()
                            if action.get('sha256') != digest(content):
                                raise ValueError('Downloaded media does not match source fixture')
                            downloads.append({'sha256': digest(content), 'size_bytes': len(content)})
                    else:
                        raise ValueError('Unsupported capture action')
                assertions = step.get('assertions', [])
                if not assertions:
                    raise ValueError('Each screenshot step must assert an expected result')
                for assertion in assertions:
                    target = page.locator(assertion['selector'])
                    if 'text' in assertion:
                        expect(target).to_contain_text(assertion['text'])
                    else:
                        expect(target).to_be_visible()
                text = page.locator('body').inner_text()
                check_text(text)
                if '(demo)' in text.lower():
                    raise ValueError('Rendered Core UI entered static demo fallback')
                live_evidence = live_core_evidence(page, url)
                persisted = persistence_evidence(page, url, proof_contract, index)
                # Credentials and unreviewed form content must never enter a screenshot.
                if page.locator('input[type=password]').count():
                    raise ValueError('Credential field found in screenshot')
                for field in page.locator('input,textarea').all():
                    check_text(field.input_value())
                name = guide['id'] + '-step-' + str(index) + '.png'
                page.screenshot(path=str(output / name), animations='disabled', full_page=True)
                records.append({'step': index, 'file': name, 'sha256': digest((output / name).read_bytes()),
                                'assertions': assertions, 'downloads': downloads, 'page_text_sha256': digest(text.encode())})
                records[-1]['live_core'] = live_evidence
                records[-1]['persistence'] = persisted
            results[guide['id']] = records
        context.close()
        browser.close()
    return {'identity': identity, 'guides': results}
