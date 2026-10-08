import json
from pathlib import Path
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from proofdesk.server import make_server

class ProtocolConventionsTests(unittest.TestCase):
    def test_unknown_tool_is_protocol_error_and_post_only_transport_advertises_allow(self):
        with tempfile.TemporaryDirectory() as temp:
            server=make_server(0,Path(temp));thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            url=f'http://127.0.0.1:{server.server_port}/mcp'
            try:
                body={'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':'unknown_mathematical_tool','arguments':{}}}
                with urllib.request.urlopen(urllib.request.Request(url,json.dumps(body).encode(),{'Content-Type':'application/json'})) as response:
                    self.assertEqual(json.load(response)['error']['code'],-32602)
                body['params']['name']=['invalid type']
                with urllib.request.urlopen(urllib.request.Request(url,json.dumps(body).encode(),{'Content-Type':'application/json'})) as response:
                    self.assertEqual(json.load(response)['error']['code'],-32602)
                with self.assertRaises(urllib.error.HTTPError) as error:urllib.request.urlopen(url)
                self.assertEqual(error.exception.code,405);self.assertEqual(error.exception.headers['Allow'],'POST')
            finally:server.shutdown();server.server_close();thread.join()
