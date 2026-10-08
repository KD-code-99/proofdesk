"""Fixed-budget comparison on automatically constructed mathematical controls.

Oracle formulas are retained for audit but are NOT passed to either search.
These are known mathematical families, not evidence of historical novelty or
better frontier-model weights. The budget matches verifier calls, not FLOPs.
"""

from __future__ import annotations

import json
import random
import time
from datetime import datetime, timezone
from pathlib import Path

from .algebra import parse
from .engine import inspect_candidate, replay, search
from .goals import Goal, digest


def fixtures(seed=7319007):
    rng = random.Random(seed)
    result = []
    for i in range(4):
        a, b = rng.choice((-3, -1, 0, 1, 3, 4)), rng.choice((-5, -2, 1, 3, 6))
        result.append((Goal(f"affine-{i}", ["x", "y"], ["y", f"({a})*y-x+({b})"], 2), f"x**2+y**2-({a})*x*y-({b})*(x+y)", True))
    for i in range(3):
        a, b = rng.choice((-3, -1, 1, 2)), rng.choice((-2, -1, 1, 3))
        q = f"({a})*x**2+({b})*x"
        u = f"(y+({q}))"
        result.append((Goal(f"nonlinear-{i}", ["x", "y"], [u, f"-x-(({a})*{u}**2+({b})*{u})"], 4), f"x**2+(y+({q}))**2", True))
    for i in range(2):
        a, b, c = [rng.choice((-3, -1, 1, 2, 3)) for _ in range(3)]
        result.append((Goal(f"summation-{i}", ["x", "y"], ["x+1", f"y+({a})*x**3+({b})*x**2+({c})*x"], 4), f"y-({a})*x**2*(x-1)**2/4-({b})*(x-1)*x*(2*x-1)/6-({c})*(x-1)*x/2", True))
    result.append((Goal("symbolic-parameters", ["x", "y", "a", "b"], ["y", "a*y-x+b", "a", "b"], 3, ("a", "b")), "x**2+y**2-a*x*y-b*(x+y)", True))
    for i in range(2):
        a, b = rng.choice((2, 3, 5)), rng.choice((2, 3, 7))
        result.append((Goal(f"expanding-{i}", ["x", "y"], [f"{a}*x", f"{b}*y"], 4), None, False))
    return result


def run_benchmark(out, budget=64, seed=20261007, seconds=30):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    cases = fixtures()
    contract = {"schema_version": 1, "fixture_seed": 7319007, "search_seed": seed, "budget": {"maximum_certificate_checks_per_task": budget, "cooperative_wall_seconds_per_task": seconds}, "matching": "Identical goals, degree bounds, representation, proof checker, and maximum certificate-check budget. CEGIS additionally uses exact linear solves; computation costs are reported separately.", "tasks": [{"goal": g.as_dict(), "oracle_invariant": oracle, "has_invariant": positive} for g, oracle, positive in cases], "non_claims": ["No historical novelty", "No model improvement", "No reproduction of the unreleased OpenAI model", "Not an equal-FLOP or equal-inference-budget comparison"]}
    contract["contract_hash"] = digest(contract)
    (out / "contract.json").write_text(json.dumps(contract, indent=2), encoding="utf-8")
    started = datetime.now(timezone.utc).isoformat()
    start = time.monotonic()
    rows, runs, fault_controls = [], {}, []
    for g, oracle, positive in cases:
        if oracle:
            control = inspect_candidate(g, parse(oracle, g.variables))
            if control["verification"]["status"] != "CERTIFIED_POLYNOMIAL_IDENTITY":
                raise AssertionError("Mathematical fixture oracle failed independent certification")
            fault = inspect_candidate(g, parse(f"({oracle})+x", g.variables))
            fault_controls.append({"goal": g.id, "certificate": fault["certificate"], "verification": fault["verification"]})
            if fault["verification"]["status"] != "REFUTED":
                raise AssertionError("Fault control was not rejected")
        row = {"goal": g.id, "positive": positive, "strategies": {}}
        for strategy in ("random", "full_symbolic", "cegis"):
            run = search(g, strategy=strategy, budget=budget, seed=seed, seconds=seconds)
            replay(run)
            runs[f"{g.id}/{strategy}"] = run
            row["strategies"][strategy] = {"status": run["status"], "metrics": run["metrics"], "formula": run["accepted"][0]["formula"] if run["accepted"] else None}
        rows.append(row)
    summary = {}
    for strategy in ("random", "full_symbolic", "cegis"):
        summary[strategy] = {"verified_invariant_tasks": sum(r["strategies"][strategy]["status"] == "CERTIFIED_INVARIANT" for r in rows), "certified_exclusion_tasks": sum(r["strategies"][strategy]["status"] == "CERTIFIED_TEMPLATE_EXCLUSION" for r in rows), "false_acceptances": sum(not r["positive"] and r["strategies"][strategy]["status"] == "CERTIFIED_INVARIANT" for r in rows), "certificate_checks": sum(r["strategies"][strategy]["metrics"]["certificate_checks"] for r in rows), "linear_solves": sum(r["strategies"][strategy]["metrics"]["linear_solves"] for r in rows), "runtime_seconds": sum(r["strategies"][strategy]["metrics"]["runtime_seconds"] for r in rows)}
    report = {"schema_version": 1, "contract_hash": contract["contract_hash"], "started_at": started, "runtime_seconds": time.monotonic() - start, "summary": summary, "tasks": rows, "fault_controls_rejected": len(fault_controls), "observed_gain_over_random": summary["cegis"]["verified_invariant_tasks"] - summary["random"]["verified_invariant_tasks"], "observed_gain_over_full_symbolic": summary["cegis"]["verified_invariant_tasks"] - summary["full_symbolic"]["verified_invariant_tasks"], "interpretation": "Comparison with both a random proposal baseline and a conventional exact symbolic solver on fixed known mathematical controls under matched certificate-check caps. Costs are measured separately. No claim of historically novel mathematics or superiority to the unreleased model.", "historically_novel_results_verified": 0, "model_weights_changed": False}
    (out / "benchmark.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (out / "runs.json").write_text(json.dumps(runs, indent=2), encoding="utf-8")
    (out / "fault-controls.json").write_text(json.dumps(fault_controls, indent=2), encoding="utf-8")
    lines = ["# Search comparison", "", report["interpretation"], "", contract["matching"], "", "| Strategy | Certified invariant tasks | Certified exclusions | Checks | Linear solves | Seconds |", "|---|---:|---:|---:|---:|---:|"]
    for name, s in summary.items():
        lines.append(f"| {name} | {s['verified_invariant_tasks']} | {s['certified_exclusion_tasks']} | {s['certificate_checks']} | {s['linear_solves']} | {s['runtime_seconds']:.3f} |")
    lines += ["", f"Rejected {len(fault_controls)} deliberately corrupted positive controls. False acceptances: {sum(s['false_acceptances'] for s in summary.values())}.", "", "Historical novelty: unestablished. The fixture families are known mathematical constructions.", "", "Every proposal, counterexample, identity proof, and bounded exclusion is retained in runs.json and can be independently replayed."]
    (out / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report
