"""Content-addressed mathematical receipts; replay reconstructs the result."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import re
from .math_tools import canonical, dispatch, engine_hashes


def create(tool, arguments, result):
    body = {"schema_version": 1, "tool": tool, "arguments": arguments, "result": result, "engine_sha256": engine_hashes()}
    return {**body, "receipt_id": hashlib.sha256(canonical(body)).hexdigest()}


def replay(receipt):
    if not isinstance(receipt, dict) or "receipt_id" not in receipt:
        raise ValueError("Missing receipt identity")
    body = {k: v for k, v in receipt.items() if k != "receipt_id"}
    if hashlib.sha256(canonical(body)).hexdigest() != receipt["receipt_id"]:
        raise ValueError("Receipt content has changed")
    if receipt.get("engine_sha256") != engine_hashes():
        raise ValueError("Receipt engine hashes differ from this release")
    actual = dispatch(receipt["tool"], receipt["arguments"])
    if canonical(actual) != canonical(receipt["result"]):
        raise ValueError("The tool result did not reproduce")
    return {"status": "REPLAY_PASSED", "receipt_id": receipt["receipt_id"], "mathematical_status": actual["status"]}


class Store:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
    def save(self, receipt):
        identity = receipt["receipt_id"]
        path = self.directory / (identity + ".json")
        if not path.exists():
            path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        return identity
    def read(self, identity):
        if not re.fullmatch(r"[a-f0-9]{64}", identity):
            raise ValueError("Invalid receipt identity")
        return json.loads((self.directory / (identity + ".json")).read_text(encoding="utf-8"))
