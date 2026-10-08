"""Replay saved mathematical evidence without importing any noetherforge/search code.

Usage: python -I -B noetherforge/recheck.py noetherforge/evidence/audit-003/benchmark
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

spec = importlib.util.spec_from_file_location("independent_proof_verifier",Path(__file__).with_name("verifier.py"))
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def run_evidence(run):
    verified = 0
    certificates = []
    for event in run["events"]:
        if "certificate" not in event:
            continue
        cert = event["certificate"]
        if cert["goal"] != run["goal"] or cert["map_hash"] != run["map_hash"]:
            raise ValueError("A proposal belongs to the wrong mathematical goal")
        if checker.verify(cert) != event["verification"]:
            raise ValueError("Saved proposal evidence does not replay")
        if event.get("novelty_evidence") and checker.verify(event["novelty_evidence"])["status"] != "CERTIFIED_POLYNOMIAL_CONSEQUENCE":
            raise ValueError("Saved consequence proof does not replay")
        certificates.append(cert)
        verified += 1
    if len(certificates) != run["metrics"]["certificate_checks"]:
        raise ValueError("Reported check count does not match the retained proposals")
    for result in run["accepted"]:
        if result["certificate"] not in certificates or checker.verify(result["certificate"])["status"] != "CERTIFIED_POLYNOMIAL_IDENTITY":
            raise ValueError("Accepted statement lacks a matching independently valid proposal")
    for result in run["exclusions"]:
        cert = result["certificate"]
        if cert["goal"] != run["goal"] or cert["map_hash"] != run["map_hash"] or checker.verify(cert) != result["verification"]:
            raise ValueError("Template exclusion does not replay")
        verified += 1
    if run["status"] == "CERTIFIED_INVARIANT" and not run["accepted"]:
        raise ValueError("Success without a verified invariant")
    if run["status"] == "CERTIFIED_TEMPLATE_EXCLUSION":
        if not run["exclusions"] or run["exclusions"][-1]["degree"] != run["goal"]["max_degree"] or run["exclusions"][-1]["verification"]["status"] != "CERTIFIED_TEMPLATE_EXCLUSION":
            raise ValueError("Exclusion does not cover the declared degree bound")
    return verified


def benchmark_evidence(directory):
    directory = Path(directory)
    contract, report, runs, faults = [load(directory/name) for name in ("contract.json","benchmark.json","runs.json","fault-controls.json")]
    bare = {k:v for k,v in contract.items() if k != "contract_hash"}
    h = hashlib.sha256(json.dumps(bare,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()).hexdigest()
    if h != contract["contract_hash"] or h != report["contract_hash"]:
        raise ValueError("Benchmark contract hash mismatch")
    tasks = {t["goal"]["id"]:t for t in contract["tasks"]}
    counts = {s:{"verified_invariant_tasks":0,"certified_exclusion_tasks":0,"false_acceptances":0,"certificate_checks":0,"linear_solves":0} for s in report["summary"]}
    records = 0
    for key,run in runs.items():
        goal_id,strategy = key.split("/")
        if run["goal"] != tasks[goal_id]["goal"] or run["strategy"] != strategy:
            raise ValueError("Benchmark run does not match its contract")
        records += run_evidence(run)
        counts[strategy]["verified_invariant_tasks"] += run["status"] == "CERTIFIED_INVARIANT"
        counts[strategy]["certified_exclusion_tasks"] += run["status"] == "CERTIFIED_TEMPLATE_EXCLUSION"
        counts[strategy]["false_acceptances"] += not tasks[goal_id]["has_invariant"] and run["status"] == "CERTIFIED_INVARIANT"
        for field in ("certificate_checks","linear_solves"):
            counts[strategy][field] += run["metrics"][field]
    if len(runs) != len(tasks)*len(counts):
        raise ValueError("Missing benchmark runs")
    for strategy,values in counts.items():
        for field,expected in values.items():
            if expected != report["summary"][strategy][field]:
                raise ValueError(f"Benchmark summary disagrees on {strategy}/{field}")
    for fault in faults:
        if checker.verify(fault["certificate"]) != fault["verification"] or fault["verification"]["status"] != "REFUTED":
            raise ValueError("Fault control was not rejected by independent replay")
    if len(faults) != report["fault_controls_rejected"]:
        raise ValueError("Fault-control count mismatch")
    if report.get("historically_novel_results_verified") != 0:
        raise ValueError("This benchmark provides no evidence of historical novelty")
    return {"status":"INDEPENDENT_REPLAY_VERIFIED","runs":len(runs),"mathematical_evidence_records":records,"fault_controls_rejected":len(faults),"summary":counts,"provenance_note":"Search execution, linear-solve counts, and timing are recorded measurements, not reconstructed by this mathematical replay"}


if __name__ == "__main__":
    try:
        source = Path(sys.argv[1])
        result = benchmark_evidence(source) if source.is_dir() else {"status":"INDEPENDENT_REPLAY_VERIFIED","mathematical_evidence_records":run_evidence(load(source))}
        print(json.dumps(result,indent=2))
    except (ValueError,KeyError,OSError) as error:
        print(json.dumps({"status":"REPLAY_FAILED","reason":str(error)}))
        raise SystemExit(1)
