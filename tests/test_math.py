import copy
import tempfile
import threading
import unittest
import json
from fractions import Fraction
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from proofdesk.math_tools import dispatch
from proofdesk.receipts import create, replay
from proofdesk.server import make_server

class MathematicsTests(unittest.TestCase):
    def test_conserved_rational_quantity(self):
        r=dispatch('check_invariant',{'numerator':'(x+1)*(y+1)*(x+y+a)','denominator':'x*y'})
        self.assertEqual(r['status'],'CERTIFIED_RATIONAL_INVARIANT')
        self.assertGreater(r['verification']['domain_nonzero_guard_count'],0)
    def test_counterexample_is_admissible_and_reproduces(self):
        r=dispatch('check_invariant',{'numerator':'x+y','denominator':'1'})
        self.assertEqual(r['status'],'REFUTED')
        p={k:Fraction(v) for k,v in r['counterexample'].items()}
        self.assertNotEqual(p['x'],0)
        self.assertNotEqual(p['x']+p['y'],p['y']+(p['a']+p['y'])/p['x'])
    def test_parameter_only_is_not_discovery(self):
        r=dispatch('check_invariant',{'numerator':'a*x*y','denominator':'x*y'})
        self.assertEqual(r['status'],'TRIVIAL_PARAMETER_FUNCTION')
    def test_fibonacci_against_independent_direct_iteration(self):
        for m in (1,2,97,1000000007):
            a,b=0,1
            for n in range(150):
                r=dispatch('recurrence_jump',{'steps':str(n),'modulus':str(m)})
                self.assertEqual(int(r['value']),a % m)
                a,b=b,a+b
    def test_affine_against_direct_iteration(self):
        for m in (1,3,101):
            value=42
            for n in range(80):
                r=dispatch('recurrence_jump',{'family':'affine','steps':str(n),'modulus':str(m),'coefficient':7,'increment':5,'seed':42})
                self.assertEqual(int(r['value']),value % m)
                value=(7*value+5) % m
    def test_sharp_bound_and_invalid_certificate(self):
        self.assertEqual(dispatch('check_inequality',{'bound':'2'})['status'],'CERTIFIED_SHARP_INEQUALITY')
        bad=dispatch('check_inequality',{'bound':'3'})
        self.assertEqual(bad['status'],'INVALID_CERTIFICATE')
        self.assertIn('not itself a counterexample',bad['explanation'])
    def test_receipt_detects_tampering_and_replays(self):
        args={'steps':'1000000000000000000000000000000','modulus':'97'}
        receipt=create('recurrence_jump',args,dispatch('recurrence_jump',args))
        self.assertEqual(replay(receipt)['status'],'REPLAY_PASSED')
        bad=copy.deepcopy(receipt);bad['result']['value']='123'
        with self.assertRaises(ValueError):replay(bad)
    def test_rejects_code_floats_and_unbounded_integer_output(self):
        for expr in ("__import__('os').getcwd()",'0.1*x','x.__class__'):
            with self.subTest(expr=expr),self.assertRaises((ValueError,SyntaxError)):
                dispatch('check_invariant',{'numerator':expr,'denominator':'1'})
        with self.assertRaises(ValueError):dispatch('recurrence_jump',{'steps':'-1','modulus':'97'})
        with self.assertRaises(ValueError):dispatch('recurrence_jump',{'steps':'10','modulus':'0'})

class TransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.server=make_server(0,cls.tmp.name)
        cls.worker=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.worker.start()
        cls.url=f'http://127.0.0.1:{cls.server.server_port}'
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.worker.join();cls.tmp.cleanup()
    def call(self,path,data,headers=None):
        request=Request(self.url+path,json.dumps(data).encode(),{'Content-Type':'application/json','Accept':'application/json, text/event-stream',**(headers or {})})
        with urlopen(request) as r:return r.status, r.read()
    def test_initialize_list_and_real_tool_call(self):
        _,body=self.call('/mcp',{'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2025-11-25','capabilities':{},'clientInfo':{'name':'test','version':'1'}}})
        self.assertEqual(json.loads(body)['result']['protocolVersion'],'2025-11-25')
        _,body=self.call('/mcp',{'jsonrpc':'2.0','id':2,'method':'tools/list'})
        self.assertEqual(len(json.loads(body)['result']['tools']),3)
        _,body=self.call('/mcp',{'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':'check_invariant','arguments':{'numerator':'x+y','denominator':'1'}}})
        self.assertEqual(json.loads(body)['result']['structuredContent']['result']['status'],'REFUTED')
    def test_notification_and_unknown_method(self):
        status,body=self.call('/mcp',{'jsonrpc':'2.0','method':'notifications/initialized'})
        self.assertEqual((status,body),(202,b''))
        _,body=self.call('/mcp',{'jsonrpc':'2.0','id':4,'method':'missing'})
        self.assertEqual(json.loads(body)['error']['code'],-32601)
    def test_browser_receipt_replay_and_origin_refusal(self):
        _,body=self.call('/api/run',{'tool':'check_inequality','arguments':{'bound':'2'}})
        receipt=json.loads(body)['receipt']
        _,body=self.call('/api/replay',{'receipt':receipt})
        self.assertEqual(json.loads(body)['status'],'REPLAY_PASSED')
        with self.assertRaises(HTTPError) as caught:self.call('/api/run',{'tool':'check_inequality'},{'Origin':'https://unrelated.example'})
        self.assertEqual(caught.exception.code,403)

if __name__=='__main__':unittest.main()
