import copy
from concurrent.futures import ThreadPoolExecutor
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.request import Request, urlopen

from proofdesk.math_tools import canonical, dispatch, engine_hashes
from proofdesk.receipts import create, replay, Store
from proofdesk.investigations import Investigations, audit_bundle
from proofdesk.server import make_server, SCHEMAS


class ExplorationTests(unittest.TestCase):
    def test_engine_hashes_are_portable_across_checkout_line_endings(self):
        expected = engine_hashes()
        original = Path.read_bytes
        def windows_lines(path):
            return original(path).replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
        with patch.object(Path, "read_bytes", windows_lines):
            self.assertEqual(engine_hashes(), expected)
    def test_synthesis_uses_counterexamples_then_certifies_and_replays(self):
        args = {"denominator": "x*y", "max_degree": 3}
        result = dispatch("discover_invariant", args)
        self.assertEqual(result["status"], "CERTIFIED_RATIONAL_INVARIANT")
        self.assertGreater(result["search"]["checks_used"], 1)
        self.assertTrue(any(a.get("counterexample") for a in result["search"]["attempts"]))
        found = result["search"]["attempts"][-1]
        self.assertEqual(dispatch("check_invariant", found)["status"], "CERTIFIED_RATIONAL_INVARIANT")
        self.assertEqual(replay(create("discover_invariant", args, result))["status"], "REPLAY_PASSED")

    def test_synthesis_handles_a_different_map(self):
        args = {"variables": ["x", "y"], "parameters": [], "transitions": ["y", "-x"], "denominator": "1", "max_degree": 2}
        result = dispatch("discover_invariant", args)
        self.assertEqual(result["status"], "CERTIFIED_RATIONAL_INVARIANT")
        self.assertEqual(result["certificate"]["goal"]["transitions"], ["y", "-x"])

    def test_search_limits_are_inconclusive(self):
        for args in ({"denominator":"x*y", "max_checks":1}, {"variables":["x"], "parameters":[], "transitions":["x+1"], "denominator":"1"}):
            result = dispatch("discover_invariant", args)
            self.assertEqual(result["status"], "NO_RESULT_WITHIN_TEMPLATE")
            self.assertIn("inconclusive", result["scope"])

    def test_invalid_budgets_and_seed_are_rejected(self):
        for tool, args in [("discover_invariant", {"max_degree":4}), ("discover_invariant", {"max_checks":0}), ("trace_orbit", {"steps":25}), ("trace_orbit", {"seed":["1/0","1","1"]}), ("trace_orbit", {"seed":["bad"]})]:
            with self.subTest(tool=tool, args=args), self.assertRaises((ValueError, ZeroDivisionError)):
                dispatch(tool, args)

    def test_exact_orbit_matches_independent_iteration(self):
        r = dispatch("trace_orbit", {"numerator":"x+y", "denominator":"1", "seed":["2","3","2"], "steps":8})
        x,y,a=Fraction(2),Fraction(3),Fraction(2)
        for row in r["rows"]:
            self.assertEqual(row["state"], {"x":str(x),"y":str(y),"a":str(a)})
            self.assertEqual(Fraction(row["quantity"]), x+y)
            x,y=y,(a+y)/x
        self.assertIn("not a proof", r["scope"])

    def test_singular_orbit_stops_without_fabricating_values(self):
        r=dispatch("trace_orbit", {"numerator":"x+y", "denominator":"1", "seed":["0","1","1"]})
        self.assertEqual(r["status"], "ORBIT_STOPPED")
        self.assertEqual(len(r["rows"]), 1)

    def test_counterexample_shows_before_and_after(self):
        r=dispatch("check_invariant", {"numerator":"x+y", "denominator":"1"})
        self.assertNotEqual(Fraction(r["witness"]["before"]), Fraction(r["witness"]["after"]))


class InvestigationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.receipts=Store(Path(self.temp.name)/"receipts")
        self.cases=Investigations(Path(self.temp.name)/"cases",self.receipts)
        self.doc=self.cases.call("start_investigation", {})["investigation"]
    def tearDown(self):
        self.temp.cleanup()
    def advance(self, action):
        self.doc=self.cases.call("advance_investigation", {"investigation_id":self.doc["id"],"expected_revision":self.doc["revision"],"action":action})["investigation"]
        return self.doc
    def test_complete_flow_survives_restart_and_exports_all_evidence(self):
        for action in ("check","discover","trace","replay"):
            self.advance(action)
        resumed=Investigations(self.cases.directory,self.receipts).read(self.doc["id"])
        self.assertEqual(resumed["revision"],4)
        self.assertIsNotNone(resumed["active_quantity"])
        self.assertEqual(len(set(row["quantity"] for row in resumed["latest"]["result"]["rows"])),1)
        bundle=self.cases.call("export_investigation", {"investigation_id":self.doc["id"]})["bundle"]
        self.assertEqual(audit_bundle(bundle)["receipts_replayed"],3)
        self.assertEqual(audit_bundle(bundle)["events"],4)
    def test_stale_revision_does_not_append_event(self):
        self.advance("check")
        with self.assertRaisesRegex(ValueError,"another session"):
            self.cases.call("advance_investigation", {"investigation_id":self.doc["id"],"expected_revision":0,"action":"trace"})
        self.assertEqual(self.cases.read(self.doc["id"])["revision"],1)
    def test_concurrent_clients_cannot_overwrite_each_other(self):
        def submit():
            try:
                self.cases.call("advance_investigation", {"investigation_id":self.doc["id"],"expected_revision":0,"action":"check"})
                return "saved"
            except ValueError:
                return "conflict"
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda _:submit(),range(2)))
        self.assertCountEqual(results,["saved","conflict"])
    def test_modified_bundle_and_forged_result_are_rejected(self):
        self.advance("check")
        bundle=self.cases.call("export_investigation", {"investigation_id":self.doc["id"]})["bundle"]
        tampered=copy.deepcopy(bundle);tampered["investigation"]["title"]="Changed"
        with self.assertRaisesRegex(ValueError,"content has changed"):audit_bundle(tampered)
        # Even a recomputed digest cannot make a false mathematical result replay.
        tampered=copy.deepcopy(bundle)
        receipt=next(iter(tampered["receipts"].values()));receipt["result"]["status"]="CERTIFIED_RATIONAL_INVARIANT"
        body={k:v for k,v in receipt.items() if k!="receipt_id"}
        identity=hashlib.sha256(canonical(body)).hexdigest();receipt["receipt_id"]=identity
        tampered["receipts"]={identity:receipt};tampered["investigation"]["events"][0]["receipt_id"]=identity
        tampered["investigation"]["events"][0]["status"]="CERTIFIED_RATIONAL_INVARIANT"
        tampered["bundle_sha256"]=hashlib.sha256(canonical({k:v for k,v in tampered.items() if k!="bundle_sha256"})).hexdigest()
        with self.assertRaisesRegex(ValueError,"did not reproduce"):audit_bundle(tampered)
    def test_bundle_rejects_forged_event_verdict(self):
        self.advance("check")
        bundle=self.cases.call("export_investigation", {"investigation_id":self.doc["id"]})["bundle"]
        bundle["investigation"]["events"][0]["status"]="CERTIFIED_RATIONAL_INVARIANT"
        bundle["bundle_sha256"]=hashlib.sha256(canonical({k:v for k,v in bundle.items() if k!="bundle_sha256"})).hexdigest()
        with self.assertRaisesRegex(ValueError,"verdict does not match"):audit_bundle(bundle)
    def test_invalid_ids_and_replay_before_check_are_rejected(self):
        with self.assertRaises(ValueError):self.cases.read("../receipt")
        with self.assertRaisesRegex(ValueError,"before replaying"):self.advance("replay")
        self.assertEqual(self.cases.read(self.doc["id"])["revision"],0)


class InvestigationProtocolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.server=make_server(0,cls.temp.name)
        cls.worker=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.worker.start()
        cls.url=f"http://127.0.0.1:{cls.server.server_port}"
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.worker.join();cls.temp.cleanup()
    def rpc(self,method,params=None):
        body={"jsonrpc":"2.0","id":42,"method":method,"params":params or {}}
        with urlopen(Request(self.url+"/mcp",json.dumps(body).encode(),{"Content-Type":"application/json","MCP-Protocol-Version":"2025-11-25"})) as response:
            data=json.load(response)
        self.assertEqual(data["id"],42)
        return data
    def tool(self,name,args):
        response=self.rpc("tools/call", {"name":name,"arguments":args})["result"]
        self.assertFalse(response["isError"])
        return response["structuredContent"]
    def test_stateful_catalog_resources_and_saved_mcp_receipts(self):
        catalog=self.rpc("tools/list")["result"]["tools"]
        self.assertEqual(len(catalog),10)
        self.assertFalse(next(t for t in catalog if t["name"]=="advance_investigation")["annotations"]["readOnlyHint"])
        self.assertEqual(set(SCHEMAS),{t["name"] for t in catalog})
        doc=self.tool("start_investigation",{})["investigation"]
        doc=self.tool("advance_investigation",{"investigation_id":doc["id"],"expected_revision":0,"action":"check"})["investigation"]
        resource=self.rpc("resources/read",{"uri":doc["resource_uri"]})["result"]["contents"][0]
        self.assertEqual(json.loads(resource["text"])["revision"],1)
        self.assertIn(doc["resource_uri"],[r["uri"] for r in self.rpc("resources/list")["result"]["resources"]])
        receipt=self.tool("check_invariant",{"numerator":"x+y","denominator":"1"})["receipt"]
        fetched=self.rpc("resources/read",{"uri":f"proofdesk://receipts/{receipt['receipt_id']}"})["result"]
        self.assertEqual(json.loads(fetched["contents"][0]["text"]),receipt)
    def test_bad_resource_returns_correlated_error(self):
        response=self.rpc("resources/read",{"uri":"proofdesk://receipts/../../secret"})
        self.assertEqual(response["error"]["code"],-32002)
    def test_stale_tool_write_is_an_actionable_tool_error(self):
        doc=self.tool("start_investigation",{})["investigation"]
        response=self.rpc("tools/call",{"name":"advance_investigation","arguments":{"investigation_id":doc["id"],"expected_revision":9,"action":"check"}})["result"]
        self.assertTrue(response["isError"])
        self.assertIn("another session",response["content"][0]["text"])
