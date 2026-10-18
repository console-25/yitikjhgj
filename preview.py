#!/usr/bin/env python3
"""Local static preview; not an application backend."""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
class PreviewHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Cache-Control', 'no-store, max-age=0')
        super().end_headers()
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8081)
    args = parser.parse_args()
    handler = partial(PreviewHandler, directory=str(Path(__file__).resolve().parent / 'site'))
    with ThreadingHTTPServer(('127.0.0.1', args.port), handler) as server:
        print(f'Noryx Hosting preview: http://127.0.0.1:{args.port}/', flush=True)
        print('Press Ctrl+C to stop. Backend services are not included.', flush=True)
        try: server.serve_forever()
        except KeyboardInterrupt: pass
