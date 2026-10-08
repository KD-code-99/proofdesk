"""Optional model proposal loop with typed mathematics and exact feedback.

The user selects the proposer argv. The default engine needs no model account.
The proposer consumes JSON on stdin and returns JSON on stdout; model-generated
expressions are parsed as data, never run as Python or shell code.
"""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

from .algebra import ResourceLimit, parse
from .corpus import packet
from .engine import inspect_candidate, search
from .goals import Goal


def evolve(index, question, proposer_argv, rounds=3, timeout=60, budget=64, archive=None):
    if not isinstance(proposer_argv, list) or not proposer_argv or any(not isinstance(a, str) for a in proposer_argv):
        raise ValueError("Provide an explicit proposer argv list")
    if not 1 <= rounds <= 20 or not 1 <= timeout <= 3600:
        raise ValueError("Invalid proposal round or timeout cap")
    context = packet(index, question)
    feedback = []
    results = []
    for round_id in range(1, rounds + 1):
        request = {"round": round_id, "research_packet": context, "feedback": feedback, "response_format": "One JSON object with goal, optional polynomial invariant, and mathematical_motivation. Goal kind may be polynomial_recurrence, rational_recurrence, inequality, or inequality_atlas. Rational goals declare transitions, fixed parameters and numerator/denominator degree bounds. Inequalities declare polynomial, reference, nonnegative assumptions and optional optimization. Atlases declare one parameter, exact probe points and the full parameter range. Supply expressions as data, never executable code. Include a precise source-to-problem connection; source claims still require verification."}
        started = time.monotonic()
        try:
            proc = subprocess.run(proposer_argv, input=json.dumps(request), encoding="utf-8", errors="strict", stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, shell=False)
            if proc.returncode:
                raise ValueError(f"Proposer exited with status {proc.returncode}")
            if len(proc.stdout) > 100000:
                raise ValueError("Proposer response exceeded 100000 characters")
            proposal = json.loads(proc.stdout)
            definition = proposal['goal']
            kind = definition.get('kind','polynomial_recurrence')
            goal = Goal.from_dict(definition) if kind=='polynomial_recurrence' else None
            motivation = proposal.get("mathematical_motivation")
            if not isinstance(motivation, str) or not motivation.strip():
                raise ValueError("Proposal must explain the mathematical motivation")
            if kind!='polynomial_recurrence':
                from .laboratory import invent
                result=invent(definition,budget=budget,seconds=min(timeout,90))
            elif "invariant" in proposal:
                result = inspect_candidate(goal, parse(proposal["invariant"], goal.variables), archive)
            else:
                result = search(goal, strategy="full_symbolic", budget=budget, archive=archive)
            record = {"round": round_id, "proposal": proposal, "result": result, "status": result.get("status", result.get("verification", {}).get("status")), "runtime_seconds": time.monotonic() - started}
            # Exact counterexamples and failed hypotheses are returned to the next model call.
            feedback.append({"round": round_id, "goal": goal.as_dict() if goal else definition, "result": result, "instruction": "Use the actual counterexample, domain restriction, certificate or proved parameter regime to change the next statement. Explain the changed mathematical mechanism. Derived formulas are not independent discoveries; historical novelty needs a source review."})
            results.append(record)
        except (ValueError, KeyError, TypeError, OSError, ResourceLimit, subprocess.TimeoutExpired) as error:
            record = {"round": round_id, "status": "INVALID_OR_UNAVAILABLE_PROPOSAL", "reason": str(error), "runtime_seconds": time.monotonic() - started}
            feedback.append(record)
            results.append(record)
    return {"schema_version": 1, "question": question, "corpus_commit": index["upstream_commit"], "rounds": results, "model_weights_changed": False, "historical_novelty": "UNREVIEWED", "scope": "Proposals are accepted as mathematics only when the exact supported proof obligation passes. General research routes remain proposals until independently proved."}


def export_lean(certificate, target):
    from . import algebra as A
    from .verifier import verify

    if verify(certificate)["status"] != "CERTIFIED_POLYNOMIAL_IDENTITY":
        raise ValueError("Only certified polynomial identities can be exported")
    goal = Goal.from_dict(certificate["goal"])
    p = {tuple(t["powers"]): A.Q(t["coefficient"]) for t in certificate["candidate"]}
    names = [f"v{i}" for i in range(len(goal.variables))]
    maps = [f"({A.format_poly(m, names, lean=True)})" for m in goal.maps]
    left, right = A.format_poly(p, maps, lean=True), A.format_poly(p, names, lean=True)
    name = "mathEvolve_" + goal.id.replace("-", "_")
    text = f"import Mathlib\n\n-- Generated from an independently checked exact-rational certificate.\n-- This file is NOT Lean-verified until the compiler reports success.\n-- Transition map hash: {goal.map_hash}\ntheorem {name} ({' '.join(names)} : ℚ) :\n    {left} =\n    {right} := by\n  ring\n\n#print axioms {name}\n"
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    return {"path": str(target), "lean_status": "NOT_RUN", "independent_certificate_status": "CERTIFIED_POLYNOMIAL_IDENTITY"}
