"""Local, revisioned investigations shared by the web interface and MCP clients."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from threading import RLock
from uuid import uuid4

from .math_tools import canonical, dispatch
from .receipts import create, replay


DEFAULT_PROBLEM = {
    "variables": ["x", "y", "a"], "parameters": ["a"],
    "transitions": ["y", "(a+y)/x", "a"],
    "numerator": "x+y", "denominator": "1",
}

INVESTIGATION_TOOLS = {
    "start_investigation": "Start a persistent conjecture investigation. Defaults to the Lyness recurrence and x+y hypothesis.",
    "advance_investigation": "Advance a saved investigation by check, discover, trace or replay. Supply its current revision to prevent stale writes.",
    "get_investigation": "Resume an investigation with its problem, event history and latest exact result.",
    "list_investigations": "List saved local investigations so another assistant session can resume the work.",
    "export_investigation": "Export a portable investigation with every receipt and a content digest for independent audit.",
}


def audit_bundle(bundle):
    if not isinstance(bundle, dict) or bundle.get("schema_version") != 1:
        raise ValueError("Unsupported investigation bundle")
    body = {k: v for k, v in bundle.items() if k != "bundle_sha256"}
    if hashlib.sha256(canonical(body)).hexdigest() != bundle.get("bundle_sha256"):
        raise ValueError("Investigation bundle content has changed")
    events, receipts = bundle["investigation"]["events"], bundle["receipts"]
    if not isinstance(events, list) or not isinstance(receipts, dict) or len(events) > 64 or bundle["investigation"]["revision"] != len(events):
        raise ValueError("Invalid investigation event history")
    if set(receipts) != {e["receipt_id"] for e in events}:
        raise ValueError("Bundle evidence does not match its event history")
    action_tools = {"check": "check_invariant", "discover": "discover_invariant", "trace": "trace_orbit"}
    for index, event in enumerate(events):
        if event["revision"] != index + 1:
            raise ValueError("Investigation revisions are not sequential")
        receipt = receipts[event["receipt_id"]]
        if event["action"] == "replay":
            if not index or events[index-1]["receipt_id"] != event["receipt_id"] or event["status"] != "REPLAY_PASSED":
                raise ValueError("Replay event does not reference the preceding evidence")
        elif action_tools.get(event["action"]) != receipt["tool"] or event["status"] != receipt["result"]["status"]:
            raise ValueError("Event verdict does not match its evidence")
    for identity, receipt in receipts.items():
        if identity != receipt.get("receipt_id"):
            raise ValueError("Bundle receipt identity mismatch")
        replay(receipt)
    return {"status": "BUNDLE_REPLAY_PASSED", "receipts_replayed": len(receipts), "events": len(events), "scope": "Content integrity and mathematical replay; this is not an authorship signature or historical provenance proof."}


class Investigations:
    def __init__(self, directory, receipts):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.receipts = receipts
        self.lock = RLock()

    def path(self, identity):
        if not isinstance(identity, str) or not re.fullmatch(r"[a-f0-9]{32}", identity):
            raise ValueError("Invalid investigation identity")
        return self.directory / (identity + ".json")

    def read(self, identity):
        with self.lock:
            doc = json.loads(self.path(identity).read_text(encoding="utf-8"))
            return self.present(doc)

    def present(self, doc):
        latest = self.receipts.read(doc["events"][-1]["receipt_id"]) if doc["events"] else None
        return {**doc, "latest": latest, "resource_uri": f"proofdesk://investigations/{doc['id']}"}

    def save(self, doc):
        path = self.path(doc["id"])
        temporary = path.with_suffix("." + uuid4().hex + ".tmp")
        try:
            temporary.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)

    def catalog(self):
        with self.lock:
            docs = [json.loads(p.read_text(encoding="utf-8")) for p in self.directory.glob("*.json")]
            return [{"id": d["id"], "title": d["title"], "revision": d["revision"], "updated_at": d["updated_at"], "status": d["events"][-1]["status"] if d["events"] else "READY"} for d in sorted(docs, key=lambda d: d["updated_at"], reverse=True)[:50]]

    def call(self, name, args):
        if not isinstance(args, dict):
            raise ValueError("Expected an arguments object")
        with self.lock:
            if name == "list_investigations":
                return {"investigations": self.catalog()}
            if name == "start_investigation":
                title = args.get("title", "What survives the Lyness map?")
                if not isinstance(title, str) or not 1 <= len(title.strip()) <= 100:
                    raise ValueError("Use a title of 1–100 characters")
                problem = args.get("problem", DEFAULT_PROBLEM)
                if not isinstance(problem, dict):
                    raise ValueError("Expected a recurrence problem object")
                # Validate using the exact checker before retaining any state.
                result = dispatch("check_invariant", problem)
                goal = result["certificate"]["goal"]
                normalized = {**{k: goal[k] for k in ("variables", "parameters", "transitions")}, "numerator": problem.get("numerator", "(x+1)*(y+1)*(x+y+a)"), "denominator": problem.get("denominator", "x*y")}
                stamp = datetime.now(timezone.utc).isoformat()
                doc = {"schema_version": 1, "id": uuid4().hex, "title": title.strip(), "revision": 0, "created_at": stamp, "updated_at": stamp, "problem": normalized, "active_quantity": None, "events": []}
                self.save(doc)
                return {"investigation": self.present(doc)}
            identity = args.get("investigation_id")
            path = self.path(identity)
            try:
                doc = json.loads(path.read_text(encoding="utf-8"))
            except FileNotFoundError as error:
                raise ValueError("Investigation not found") from error
            if name == "get_investigation":
                return {"investigation": self.present(doc)}
            if name == "export_investigation":
                body = {"schema_version": 1, "investigation": doc, "receipts": {e["receipt_id"]: self.receipts.read(e["receipt_id"]) for e in doc["events"]}}
                return {"bundle": {**body, "bundle_sha256": hashlib.sha256(canonical(body)).hexdigest()}}
            if name != "advance_investigation":
                raise ValueError("Unknown investigation tool")
            if type(args.get("expected_revision")) is not int or args["expected_revision"] != doc["revision"]:
                raise ValueError("Investigation changed in another session. Resume it and retry with its current revision.")
            if len(doc["events"]) >= 64:
                raise ValueError("This investigation has reached 64 events. Export it and start another.")
            action = args.get("action")
            problem = doc["problem"]
            if action == "replay":
                if not doc["events"]:
                    raise ValueError("Run a check before replaying evidence")
                receipt = self.receipts.read(doc["events"][-1]["receipt_id"])
                result = replay(receipt)
                event_status, summary = result["status"], "Recomputed the saved evidence with matching engine hashes."
            else:
                if action == "check":
                    tool, arguments = "check_invariant", problem
                elif action == "discover":
                    tool, arguments = "discover_invariant", {**problem, "denominator": args.get("search_denominator", "x*y"), "max_degree": args.get("max_degree", 3), "max_checks": args.get("max_checks", 16)}
                elif action == "trace":
                    tool, arguments = "trace_orbit", {**problem, **(doc["active_quantity"] or {}), "seed": args.get("seed", ["1"] * len(problem["variables"])), "steps": args.get("steps", 8)}
                else:
                    raise ValueError("Choose check, discover, trace or replay")
                result = dispatch(tool, arguments)
                receipt = create(tool, arguments, result)
                self.receipts.save(receipt)
                if result["status"] == "CERTIFIED_RATIONAL_INVARIANT":
                    if action == "discover":
                        doc["active_quantity"] = {k: result["search"]["attempts"][-1][k] for k in ("numerator", "denominator")}
                    else:
                        doc["active_quantity"] = {k: problem[k] for k in ("numerator", "denominator")}
                event_status, summary = result["status"], result["explanation"]
            doc["revision"] += 1
            doc["updated_at"] = datetime.now(timezone.utc).isoformat()
            doc["events"].append({"revision": doc["revision"], "action": action, "status": event_status, "summary": summary, "receipt_id": receipt["receipt_id"]})
            self.save(doc)
            return {"investigation": self.present(doc)}
