"""A degree-growing, counterexample-guided search with persistent proof evidence."""

from __future__ import annotations

import json
import platform
import random
import sqlite3
import time
from datetime import datetime, timezone
from fractions import Fraction as Q
from pathlib import Path

from . import algebra as A
from .goals import Goal, digest
from .verifier import VerificationLimit, verify


def rows_for(goal, basis, points):
    rows = []
    for point in points:
        image = [A.evaluate(m, point) for m in goal.maps]
        rows.append([A.evaluate({m: Q(1)}, image) - A.evaluate({m: Q(1)}, point) for m in basis])
    return rows


def seed_points(dim):
    return [tuple(Q(0) for _ in range(dim))] + [tuple(Q(sign if i == j else 0) for i in range(dim)) for j in range(dim) for sign in (-1, 1)]


def candidate_key(goal, p):
    return digest({"map": goal.map_hash, "invariant_mod_scale_and_constant": A.terms(A.normalize(p))})


class Archive:
    """Store every attempted statement and its actual evidence, not just successes."""

    def __init__(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.execute("CREATE TABLE IF NOT EXISTS proposals(key TEXT PRIMARY KEY, map_hash TEXT, status TEXT, certificate TEXT, evidence TEXT, attempts INTEGER NOT NULL, last_seen TEXT)")
        self.db.commit()

    def record(self, goal, p, certificate, evidence):
        key = candidate_key(goal, p)
        prior = self.db.execute("SELECT status FROM proposals WHERE key=?", (key,)).fetchone()
        if prior and prior[0] != evidence["status"]:
            raise RuntimeError("Conflicting proof evidence for a canonical statement")
        relation = None
        novelty = "PREVIOUSLY_SEEN" if prior else "NEW_TO_LOCAL_ARCHIVE"
        if not prior and evidence["status"] == "CERTIFIED_POLYNOMIAL_IDENTITY":
            # Screen one-generator polynomial consequences, not just textual duplicates.
            # Multi-generator combinations and arbitrary equivalences remain unreviewed.
            existing = self.db.execute("SELECT certificate FROM proposals WHERE map_hash=? AND status='CERTIFIED_POLYNOMIAL_IDENTITY' ORDER BY key LIMIT 16", (goal.map_hash,)).fetchall()
            degree = max(map(sum, p))
            for (raw,) in existing:
                known = json.loads(raw)
                if verify(known)["status"] != "CERTIFIED_POLYNOMIAL_IDENTITY":
                    raise ValueError("Stored invariant no longer verifies")
                h = {tuple(t["powers"]): Q(t["coefficient"]) for t in known["candidate"]}
                h_degree = max(map(sum, h))
                powers = [A.power(h, k, len(goal.variables)) for k in range(1, degree // h_degree + 1)]
                if not powers:
                    continue
                monoms = sorted(set(p).union(*(set(q) for q in powers)))
                matrix = [[q.get(m, Q(0)) for q in powers] + [-p.get(m, Q(0))] for m in monoms]
                vectors = A.nullspace(matrix, len(powers) + 1)
                dependence = next((v for v in vectors if v[-1]), None)
                if dependence:
                    relation = {"schema_version": 1, "kind": "invariant_consequence", "target": certificate, "known": known, "coefficients": [str(c / dependence[-1]) for c in dependence[:-1]], "scope": "Rational polynomial in one previously certified invariant; other equivalences are not screened"}
                    if verify(relation)["status"] != "CERTIFIED_POLYNOMIAL_CONSEQUENCE":
                        raise AssertionError("Independent consequence checker disagrees")
                    novelty = "DERIVED_FROM_KNOWN_INVARIANT"
                    break
        self.db.execute("INSERT INTO proposals VALUES(?,?,?,?,?,1,?) ON CONFLICT(key) DO UPDATE SET attempts=attempts+1,last_seen=excluded.last_seen", (key, goal.map_hash, evidence["status"], json.dumps(certificate, sort_keys=True), json.dumps(evidence, sort_keys=True), datetime.now(timezone.utc).isoformat()))
        self.db.commit()
        return novelty, relation

    def close(self):
        self.db.close()


def inspect_candidate(goal, p, archive=None):
    p = A.normalize(p)
    cert = goal.certificate(p)
    evidence = verify(cert)
    residual = A.add(A.compose(p, goal.maps, len(goal.variables)), A.scale(p, Q(-1)))
    if (not residual) != (evidence["status"] == "CERTIFIED_POLYNOMIAL_IDENTITY"):
        raise AssertionError("Independent and search-side polynomial arithmetic disagree")
    if evidence["status"] == "REFUTED":
        point = tuple(Q(evidence["counterexample"][name]) for name in goal.variables)
        image = [A.evaluate(m, point) for m in goal.maps]
        if A.evaluate(p, point) == A.evaluate(p, image):
            raise AssertionError("Counterexample failed direct search-side evaluation")
    novelty, relation = archive.record(goal, p, cert, evidence) if archive else ("ARCHIVE_NOT_CHECKED", None)
    return {"formula": A.format_poly(p, goal.variables), "canonical_key": candidate_key(goal, p), "certificate": cert, "verification": evidence, "local_novelty": novelty, "novelty_evidence": relation, "historical_novelty": "LITERATURE_REVIEW_REQUIRED"}


def search(goal: Goal, strategy="cegis", budget=64, seed=20261007, seconds=30, archive=None):
    if strategy not in {"cegis", "random", "full_symbolic"} or not 1 <= budget <= 2000 or not 0 < seconds <= 3600:
        raise ValueError("Invalid strategy or resource budget")
    start = time.monotonic()
    deadline = start + seconds
    points = seed_points(len(goal.variables))
    events, accepted, exclusions = [], [], []
    checks, linear_solves = 0, 0
    rng = random.Random(seed)
    status = "BUDGET_EXHAUSTED"
    visited = set()
    current_degree = 0

    def consider(p, degree):
        nonlocal checks
        p = A.normalize(p)
        if not p:
            return None
        key = candidate_key(goal, p)
        if key in visited:
            return None
        visited.add(key)
        checks += 1
        result = inspect_candidate(goal, p, archive)
        events.append({"check": checks, "degree": degree, **result})
        return result

    try:
        if strategy == "full_symbolic":
            # A strong conventional baseline: solve every coefficient equation
            # of H(T)-H at once. It receives exactly the same template bounds.
            basis = A.monomials(len(goal.variables),goal.max_degree,goal.parameter_indices)
            columns = [A.add(A.compose({m:Q(1)},goal.maps,len(goal.variables)),{m:Q(-1)}) for m in basis]
            monoms = sorted(set().union(*(set(c) for c in columns)))
            matrix = [[column.get(m,Q(0)) for column in columns] for m in monoms]
            vectors = A.nullspace(matrix,len(basis),deadline=deadline)
            linear_solves = 1
            if not vectors:
                cert = {"schema_version":1,"kind":"symbolic_template_exclusion","domain":"QQ","goal":goal.as_dict(),"map_hash":goal.map_hash,"max_degree":goal.max_degree}
                evidence = verify(cert)
                exclusions.append({"degree":goal.max_degree,"certificate":cert,"verification":evidence})
                if evidence["status"] == "CERTIFIED_TEMPLATE_EXCLUSION":
                    status = "CERTIFIED_TEMPLATE_EXCLUSION"
            else:
                polynomials = [A.normalize({m:c for m,c in zip(basis,v) if c}) for v in vectors]
                polynomials.sort(key=lambda p:(max(map(sum,p)),len(p),json.dumps(A.terms(p),sort_keys=True)))
                for p in polynomials:
                    if checks >= budget:
                        break
                    result = consider(p,goal.max_degree)
                    if result and result["verification"]["status"] == "CERTIFIED_POLYNOMIAL_IDENTITY":
                        accepted.append(result)
                        status = "CERTIFIED_INVARIANT"
                        break
        elif strategy == "random":
            # The baseline has exactly the same representation and proof checker.
            # It samples a bounded sparse integer-coefficient proposal distribution.
            basis = A.monomials(len(goal.variables), goal.max_degree, goal.parameter_indices)
            draws = 0
            while checks < budget and time.monotonic() < deadline and draws < budget * 20:
                draws += 1
                support = rng.sample(basis, rng.randint(1, min(6, len(basis))))
                p = {m: Q(rng.choice((-3, -2, -1, 1, 2, 3))) for m in support}
                result = consider(p, max(map(sum, support)))
                if result and result["verification"]["status"] == "CERTIFIED_POLYNOMIAL_IDENTITY":
                    accepted.append(result)
                    status = "CERTIFIED_INVARIANT"
                    break
            if time.monotonic() >= deadline:
                status = "TIME_LIMIT"
        else:
            for degree in range(1, goal.max_degree + 1):
                current_degree = degree
                basis = A.monomials(len(goal.variables), degree, goal.parameter_indices)
                while checks < budget:
                    if time.monotonic() >= deadline:
                        status = "TIME_LIMIT"
                        break
                    vectors = A.nullspace(rows_for(goal, basis, points), len(basis), deadline=deadline)
                    linear_solves += 1
                    if not vectors:
                        exclusion = {"schema_version": 1, "kind": "template_exclusion", "domain": "QQ", "goal": goal.as_dict(), "map_hash": goal.map_hash, "max_degree": degree, "points": [[str(v) for v in p] for p in points]}
                        exclusion_evidence = verify(exclusion)
                        exclusions.append({"degree": degree, "certificate": exclusion, "verification": exclusion_evidence})
                        break
                    polynomials = [A.normalize({m: c for m, c in zip(basis, v) if c}) for v in vectors]
                    polynomials.sort(key=lambda p: (max(map(sum, p)), len(p), json.dumps(A.terms(p), sort_keys=True)))
                    learned = False
                    for p in polynomials:
                        if checks >= budget or time.monotonic() >= deadline:
                            break
                        result = consider(p, degree)
                        if not result:
                            continue
                        if result["verification"]["status"] == "CERTIFIED_POLYNOMIAL_IDENTITY":
                            accepted.append(result)
                            status = "CERTIFIED_INVARIANT"
                            break
                        witness = result["verification"]["counterexample"]
                        point = tuple(Q(witness[v]) for v in goal.variables)
                        if point in points:
                            raise AssertionError("Hypothesis contradicted a point already used to fit it")
                        points.append(point)
                        learned = True
                        if len(points) > 500:
                            raise A.ResourceLimit("The counterexample point cap was reached")
                        # Refit immediately. No further candidate is checked against stale constraints.
                        break
                    if accepted:
                        break
                    if not learned:
                        break
                if accepted or status == "TIME_LIMIT" or checks >= budget:
                    break
            if not accepted and exclusions and exclusions[-1]["degree"] == goal.max_degree and exclusions[-1]["verification"]["status"] == "CERTIFIED_TEMPLATE_EXCLUSION":
                status = "CERTIFIED_TEMPLATE_EXCLUSION"
    except (A.ResourceLimit, VerificationLimit) as error:
        status = "RESOURCE_LIMIT"
        events.append({"status": status, "reason": str(error), "degree": current_degree})

    return {"schema_version": 1, "goal": goal.as_dict(), "map_hash": goal.map_hash, "strategy": strategy, "seed": seed, "status": status, "budget": {"certificate_checks": budget, "wall_seconds_cooperative": seconds, "max_terms": A.MAX_TERMS, "max_coefficient_bits": A.MAX_BITS, "max_template_coefficients": 180, "max_counterexample_points": 500}, "metrics": {"certificate_checks": checks, "linear_solves": linear_solves, "counterexample_points": len(points) - len(seed_points(len(goal.variables))), "runtime_seconds": time.monotonic() - start}, "accepted": accepted, "events": events, "exclusions": exclusions, "interpretation": "Exact invariant identities are universal over QQ. Exhausted budgets and time limits are inconclusive. Certified exclusions apply only to the stated bounded polynomial template. Local novelty does not establish historical novelty."}


def write_run(run, out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    (out / "run.json").write_text(json.dumps(run, indent=2, ensure_ascii=False), encoding="utf-8")
    for i, result in enumerate(run["accepted"]):
        (out / f"invariant-{i + 1}.json").write_text(json.dumps(result["certificate"], indent=2), encoding="utf-8")
    if run["exclusions"]:
        (out / "exclusion.json").write_text(json.dumps(run["exclusions"][-1]["certificate"], indent=2), encoding="utf-8")
    summary = [f"# {run['goal']['id']}", "", f"Status: `{run['status']}`", "", f"Transition: `{run['goal']['transitions']}`", "", f"Checks: {run['metrics']['certificate_checks']}; exact linear solves: {run['metrics']['linear_solves']}; counterexamples learned: {run['metrics']['counterexample_points']}.", ""]
    for result in run["accepted"]:
        summary += [f"Conserved polynomial: `{result['formula']}`.", "", "Proof: independent exact distributive expansion of H(T(x)) - H(x) has no nonzero coefficients.", "", "Historical novelty: literature review required. Lean compilation: not run.", ""]
    summary += [run["interpretation"]]
    (out / "RESULT.md").write_text("\n".join(summary) + "\n", encoding="utf-8")
    return out


def replay(run):
    """Recheck both positive and negative mathematics, plus all saved counterexamples."""
    goal = Goal.from_dict(run["goal"])
    if goal.map_hash != run["map_hash"]:
        raise ValueError("Run metadata is bound to a different map")
    statuses = []

    def bound_certificate(cert):
        if cert["map_hash"] != run["map_hash"] or cert["goal"] != run["goal"]:
            raise ValueError("Evidence belongs to a different run goal")
        return verify(cert)
    for result in run["events"]:
        if "certificate" in result:
            actual = bound_certificate(result["certificate"])
            if actual != result["verification"]:
                raise ValueError("Saved candidate evidence disagrees with independent replay")
            if result.get("novelty_evidence") and verify(result["novelty_evidence"])["status"] != "CERTIFIED_POLYNOMIAL_CONSEQUENCE":
                raise ValueError("Saved local consequence evidence did not replay")
            statuses.append(actual["status"])
    for result in run["exclusions"]:
        actual = bound_certificate(result["certificate"])
        if actual != result["verification"]:
            raise ValueError("Saved template exclusion disagrees with independent replay")
        statuses.append(actual["status"])
    for result in run["accepted"]:
        if bound_certificate(result["certificate"])["status"] != "CERTIFIED_POLYNOMIAL_IDENTITY":
            raise ValueError("Accepted proof did not replay")
    if run["status"] == "CERTIFIED_INVARIANT" and not run["accepted"]:
        raise ValueError("Success status without a proof")
    if run["status"] == "CERTIFIED_TEMPLATE_EXCLUSION" and (not run["exclusions"] or verify(run["exclusions"][-1]["certificate"])["status"] != "CERTIFIED_TEMPLATE_EXCLUSION" or run["exclusions"][-1]["degree"] != run["goal"]["max_degree"]):
        raise ValueError("Template exclusion status without a complete certificate")
    return {"status": "REPLAY_VERIFIED", "mathematical_evidence_records": len(statuses), "runtime_environment": platform.python_version()}
