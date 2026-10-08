"""Local browser API and stateless MCP Streamable HTTP server."""
from __future__ import annotations
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from urllib.parse import urlparse
from .math_tools import ROOT, TOOLS, dispatch
from .receipts import Store, create, replay

SCHEMAS = {
    "check_invariant": {"type":"object","properties":{"variables":{"type":"array","items":{"type":"string"}},"transitions":{"type":"array","items":{"type":"string"}},"parameters":{"type":"array","items":{"type":"string"}},"numerator":{"type":"string"},"denominator":{"type":"string"}},"required":["numerator","denominator"],"additionalProperties":False},
    "recurrence_jump": {"type":"object","properties":{"family":{"type":"string","enum":["fibonacci","affine"]},"steps":{"type":"string"},"modulus":{"type":"string"},"coefficient":{"type":"integer"},"increment":{"type":"integer"},"seed":{"type":"integer"}},"required":["steps","modulus"],"additionalProperties":False},
    "check_inequality": {"type":"object","properties":{"bound":{"type":"string"}},"additionalProperties":False},
}


class Handler(BaseHTTPRequestHandler):
    server_version = "ProofDesk/0.1"
    def log_message(self, *args):
        pass
    def send(self, status, body, content_type="application/json"):
        raw = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        if status == 405:
            self.send_header("Allow", "POST")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self'; script-src 'self'; connect-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(raw)
    def allowed(self):
        host = self.headers.get("Host", "")
        if host not in self.server.allowed_hosts:
            return False
        origin = self.headers.get("Origin")
        return not origin or urlparse(origin).netloc == host
    def do_GET(self):
        if not self.allowed():
            return self.send(403, {"error":"Unsupported host or origin"})
        path = urlparse(self.path).path
        if path == "/health":
            return self.send(200, {"status":"ok","name":"ProofDesk","mcp_protocol":"2025-11-25"})
        if path == "/mcp":
            return self.send(405, {"error":"This stateless MCP endpoint uses POST"})
        if path.startswith("/api/receipts/"):
            try:
                return self.send(200, self.server.store.read(path.rsplit("/",1)[1]))
            except (ValueError, FileNotFoundError):
                return self.send(404, {"error":"Receipt not found"})
        names = {"/":"index.html","/app.js":"app.js","/style.css":"style.css","/favicon.svg":"favicon.svg"}
        if path not in names:
            return self.send(404, {"error":"Not found"})
        file = ROOT/"web"/names[path]
        content_type = {".html":"text/html; charset=utf-8",".js":"text/javascript; charset=utf-8",".css":"text/css; charset=utf-8",".svg":"image/svg+xml"}[file.suffix]
        return self.send(200, file.read_bytes(), content_type)
    def do_POST(self):
        if not self.allowed():
            return self.send(403, {"error":"Unsupported host or origin"})
        try:
            size = int(self.headers.get("Content-Length", 0))
            if not 0 < size <= 32768:
                return self.send(413, {"error":"Request must contain at most 32 KiB"})
            data = json.loads(self.rfile.read(size))
            if not isinstance(data, dict):
                raise ValueError("Expected a JSON object")
        except (ValueError, json.JSONDecodeError):
            return self.send(400, {"error":"Invalid JSON request"})
        path = urlparse(self.path).path
        if path == "/mcp":
            return self.mcp(data)
        try:
            if path == "/api/run":
                result = dispatch(data["tool"], data.get("arguments", {}))
                receipt = create(data["tool"], data.get("arguments", {}), result)
                self.server.store.save(receipt)
                return self.send(200, {"result":result,"receipt":receipt})
            if path == "/api/replay":
                return self.send(200, replay(data["receipt"]))
        except (ValueError, KeyError, TypeError, SyntaxError, ZeroDivisionError) as error:
            return self.send(422, {"error":str(error)[:250],"status":"UNSUPPORTED_OR_INVALID_INPUT"})
        return self.send(404, {"error":"Not found"})
    def mcp(self, data):
        identity = data.get("id")
        method = data.get("method")
        def answer(result):
            return self.send(200, {"jsonrpc":"2.0","id":identity,"result":result})
        if data.get("jsonrpc") != "2.0" or not isinstance(method, str):
            return self.send(400, {"jsonrpc":"2.0","id":identity,"error":{"code":-32600,"message":"Invalid Request"}})
        if identity is None:
            return self.send(202, b"")
        if method == "initialize":
            return answer({"protocolVersion":"2025-11-25","capabilities":{"tools":{"listChanged":False}},"serverInfo":{"name":"proofdesk","version":"0.1.1"},"instructions":"Return the tool's evidence type and domain with every mathematical answer. Never replace UNKNOWN with proof."})
        if self.headers.get("MCP-Protocol-Version", "2025-11-25") != "2025-11-25":
            return self.send(400, {"error":"Unsupported MCP protocol version"})
        if method == "ping":
            return answer({})
        if method == "tools/list":
            return answer({"tools":[{"name":name,"description":description,"inputSchema":SCHEMAS[name],"annotations":{"readOnlyHint":True,"destructiveHint":False,"openWorldHint":False}} for name,(description,_) in TOOLS.items()]})
        if method == "tools/call":
            params = data.get("params", {})
            if not isinstance(params, dict) or not isinstance(params.get("name"), str) or params.get("name") not in TOOLS:
                return self.send(200, {"jsonrpc":"2.0","id":identity,"error":{"code":-32602,"message":"Unknown mathematical tool"}})
            try:
                result = dispatch(params["name"], params.get("arguments", {}))
                receipt = create(params["name"], params.get("arguments", {}), result)
                return answer({"content":[{"type":"text","text":json.dumps({"result":result,"receipt":receipt})}],"structuredContent":{"result":result,"receipt":receipt},"isError":False})
            except (ValueError, KeyError, TypeError, SyntaxError, ZeroDivisionError) as error:
                return answer({"content":[{"type":"text","text":str(error)[:250]}],"isError":True})
        return self.send(200, {"jsonrpc":"2.0","id":identity,"error":{"code":-32601,"message":"Method not found"}})


def make_server(port=4186, state_dir=None):
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.allowed_hosts = {f"127.0.0.1:{server.server_port}",f"localhost:{server.server_port}"}
    server.store = Store(state_dir or ROOT/".state"/"receipts")
    return server


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=4186)
    parser.add_argument("--state-dir", type=Path)
    args = parser.parse_args()
    server = make_server(args.port, args.state_dir)
    print(f"ProofDesk http://127.0.0.1:{server.server_port} · MCP /mcp", flush=True)
    server.serve_forever()
