import json, os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from .routing import plan_routes, NODES
from .scoring import score_route
from .agent import chat

ROOT=Path(__file__).parent/'static'
class Handler(BaseHTTPRequestHandler):
    def _send(self, data, code=200, ctype='application/json'):
        raw=data if isinstance(data,bytes) else (json.dumps(data).encode() if ctype=='application/json' else data.encode())
        self.send_response(code); self.send_header('Content-Type',ctype); self.send_header('Content-Length',str(len(raw))); self.end_headers(); self.wfile.write(raw)
    def do_GET(self):
        p=urlparse(self.path).path
        if p=='/api/health': return self._send({'status':'ok','mode':'offline-demo'})
        if p=='/api/model/status': return self._send({'status':'fallback-ready','architecture':'custom Transformer interface','checkpoint':False,'metrics':None})
        if p=='/api/map/region': return self._send({'nodes':NODES,'region':'Offline demonstration region','data_status':'synthetic demo graph'})
        if p=='/' or p=='/index.html': return self._send((ROOT/'index.html').read_text(encoding='utf-8'),ctype='text/html')
        if p.startswith('/assets/'):
            # Static assets are stored directly in backend/app/static/, not
            # in a nested static/assets directory.
            fp=ROOT/p.removeprefix('/assets/');
            if fp.exists(): return self._send(fp.read_text(encoding='utf-8'),ctype='text/css' if fp.suffix=='.css' else 'application/javascript')
        return self._send({'error':'not found'},404)
    def do_POST(self):
        try: body=json.loads(self.rfile.read(int(self.headers.get('Content-Length',0))) or b'{}'); p=urlparse(self.path).path
        except Exception: return self._send({'error':'invalid JSON'},400)
        try:
            if p=='/api/routes/plan':
                routes=plan_routes(body.get('origin','station'),body.get('destination','campus'))
                for r in routes:r['score']=score_route(r,body.get('preferences'))
                return self._send({'routes':routes,'data_status':'synthetic demo graph'})
            if p=='/api/agent/chat': return self._send(chat(body.get('message',''),body.get('origin','station'),body.get('destination','campus')))
        except ValueError as e:return self._send({'error':str(e)},422)
        return self._send({'error':'not found'},404)

if __name__=='__main__':
    host=os.getenv('NIGHTWISE_HOST','127.0.0.1'); port=int(os.getenv('NIGHTWISE_PORT','8000')); print(f'NightWise AI at http://{host}:{port}'); ThreadingHTTPServer((host,port),Handler).serve_forever()
