"""Disposable test application; never represents a commissioned Media Nexus host."""
import json
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from .source import digest


@contextmanager
def serve(source, recipes, manifest, bindings):
    # All served product files come from the exact supplied Git revision.
    app = source.read('app.html').encode()
    contracts = {s['id']: json.loads(source.read(s['contract'])) for s in recipes['guides']}
    media = source.read('media.svg').encode()
    identity = {'source_revision': source.revision, 'version': manifest['version'],
                'modules': manifest['modules'], 'platform': manifest['platform'],
                'config_sha256': digest(manifest.get('config', {})), 'contracts': bindings,
                'synthetic': True, 'test_account': 'docs-reviewer'}
    state = {'collections': [], 'transfers': [], 'selected': []}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def send(self, body, kind='application/json', status=200, attachment=None):
            payload = json.dumps(body).encode() if kind == 'application/json' else body
            self.send_response(status)
            self.send_header('Content-Type', kind)
            self.send_header('Content-Length', str(len(payload)))
            self.send_header('Cache-Control', 'no-store')
            if attachment:
                self.send_header('Content-Disposition', 'attachment; filename="' + attachment + '"')
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self):
            if self.path == '/__vaultline_docs':
                return self.send(identity)
            if self.path == '/':
                return self.send(app, 'text/html; charset=utf-8')
            if self.path == '/api/config':
                return self.send({'manifest': manifest, 'contracts': contracts})
            if self.path == '/media.svg':
                return self.send(media, 'image/svg+xml')
            if self.headers.get('Cookie') != 'docs_session=synthetic':
                return self.send({'error': 'Synthetic test session required'}, status=401)
            if self.path == '/api/search?q=sunrise':
                return self.send({'assets': [{'id': 'sunrise', 'name': 'Synthetic Sunrise.svg'}]})
            if self.path == '/api/collections':
                return self.send(state['collections'])
            if self.path == '/api/transfer':
                return self.send(state['transfers'])
            if self.path == '/api/download' and manifest['config'].get('remoteTransfer') is True:
                return self.send(media, 'image/svg+xml', attachment='synthetic-sunrise.svg')
            self.send({'error': 'Unsupported fixture route'}, status=404)

        def do_POST(self):
            if self.path == '/api/session':
                state.update(collections=[], transfers=[], selected=[])
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Set-Cookie', 'docs_session=synthetic; HttpOnly; SameSite=Strict; Path=/')
                self.end_headers()
                return self.wfile.write(b'{"account":"docs-reviewer"}')
            if self.headers.get('Cookie') != 'docs_session=synthetic':
                return self.send({'error': 'Synthetic test session required'}, status=401)
            data = json.loads(self.rfile.read(int(self.headers.get('Content-Length', '0'))) or '{}')
            if self.path == '/api/collections' and manifest['config'].get('collections') is True:
                if data.get('ids') != ['sunrise'] or not data.get('name'):
                    return self.send({'error': 'Select media and name the collection'}, status=400)
                state['collections'].append({'name': data['name'], 'assets': data['ids']})
                return self.send({'message': 'Collection created: ' + data['name']})
            if manifest['config'].get('remoteTransfer') is not True:
                return self.send({'error': 'Transfers unavailable'}, status=403)
            if self.path == '/api/transfer':
                if data.get('ids') != ['sunrise']:
                    return self.send({'error': 'Select media first'}, status=400)
                state['transfers'] = [{'status': 'Ready', 'bytes': len(media), 'sha256': digest(media)}]
            elif self.path == '/api/interrupt' and state['transfers']:
                state['transfers'][0].update(status='Interrupted', saved_bytes=0, error='Synthetic connection interrupted')
            elif self.path == '/api/resume' and state['transfers']:
                state['transfers'][0].update(status='Ready', error=None)
            else:
                return self.send({'error': 'Unsupported action'}, status=400)
            return self.send(state['transfers'])

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        yield 'http://127.0.0.1:' + str(server.server_port)
    finally:
        server.shutdown()
        server.server_close()
        worker.join()
