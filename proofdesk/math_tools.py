"""A bounded tool surface over the independently checked NOETHER-FORGE kernel."""
from __future__ import annotations

import ast
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "vendor"))
from noetherforge import algebra as A
from noetherforge.rational import RationalGoal
from noetherforge.proofcheck import verify
from noetherforge import rational as R


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def integer(value, name, maximum):
    if isinstance(value, bool) or not re.fullmatch(r"-?\d{1,110}", str(value)):
        raise ValueError(f"{name} must be an integer")
    value = int(value)
    if not 0 <= value <= maximum:
        raise ValueError(f"{name} is outside the supported range")
    return value


def bounded_expression(text):
    if not isinstance(text, str) or not 0 < len(text) <= 400:
        raise ValueError("Expressions must contain 1–400 characters")
    tree = ast.parse(text, mode="eval")
    if sum(1 for _ in ast.walk(tree)) > 100:
        raise ValueError("Expression is too complex")
    for n in ast.walk(tree):
        if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Pow):
            if not isinstance(n.right, ast.Constant) or type(n.right.value) is not int or not 0 <= n.right.value <= 6 or any(isinstance(p, ast.BinOp) and isinstance(p.op, ast.Pow) for p in ast.walk(n.left)):
                raise ValueError('Use a literal power from 0 to 6 without nested powers')
        if isinstance(n, ast.Constant):
            if type(n.value) is not int or abs(n.value) > 10**12:
                raise ValueError("Use exact integer literals of at most 12 digits")
        if isinstance(n, (ast.Call, ast.Attribute, ast.Subscript, ast.Lambda, ast.Compare)):
            raise ValueError("Only mathematical expressions are supported")
    return text


def check_invariant(arguments):
    variables = arguments.get("variables", ["x", "y", "a"])
    transitions = arguments.get("transitions", ["y", "(a+y)/x", "a"])
    parameters = arguments.get("parameters", ["a"])
    if not isinstance(variables, list) or not 1 <= len(variables) <= 3:
        raise ValueError("Choose one to three variables")
    if len(set(variables)) != len(variables) or any(not isinstance(v, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,9}", v) for v in variables):
        raise ValueError("Variables must be distinct short mathematical names")
    if not isinstance(transitions, list) or len(transitions) != len(variables):
        raise ValueError("Provide one transition per variable")
    if not isinstance(parameters, list) or any(v not in variables for v in parameters):
        raise ValueError("Parameters must be declared variables")
    transitions = [bounded_expression(x) for x in transitions]
    numerator = bounded_expression(arguments.get("numerator", "(x+1)*(y+1)*(x+y+a)"))
    denominator = bounded_expression(arguments.get("denominator", "x*y"))
    goal = RationalGoal("proofdesk-user-program", variables, transitions, 6, 3, tuple(parameters))
    certificate = goal.certificate(A.parse(numerator, variables), A.parse(denominator, variables))
    verdict = verify(certificate)
    status = verdict["status"]
    point = verdict.get("counterexample")
    explanation = {
        "CERTIFIED_RATIONAL_INVARIANT": "The identity holds for every rational state satisfying the certificate's nonzero domain guards.",
        "REFUTED": "This proposed invariant changes. The checker found an exact admissible counterexample.",
        "TRIVIAL_PARAMETER_FUNCTION": "This expression depends only on fixed parameters; it does not describe a new state invariant.",
    }.get(status, "The checker did not certify this statement.")
    result = {"status": status, "evidence_type": "exact_symbolic_identity" if status.startswith("CERTIFIED_") else "exact_checker_verdict",
              "explanation": explanation, "verification": verdict, "certificate": certificate,
              "formula": f"({numerator}) / ({denominator})", "domain": "Rational arithmetic; original-expression nonzero guards are retained.",
              "scope": "A supported rational identity. Historical novelty and arbitrary program correctness are not claimed."}
    if point:
        result["counterexample"] = point
        state = tuple(Fraction(point[v]) for v in variables)
        quantity = R.Rational.poly(A.parse(numerator, variables), len(variables)).div(R.Rational.poly(A.parse(denominator, variables), len(variables)))
        image = tuple(m.at(state) for m in goal.maps)
        result["witness"] = {"before": str(quantity.at(state)), "after": str(quantity.at(image)), "next_state": {v: str(q) for v, q in zip(variables, image)}}
    return result


def recurrence_jump(arguments):
    n = integer(arguments.get("steps", "1000000000000000000000000000000"), "steps", 10**100)
    modulus = integer(arguments.get("modulus", "1000000007"), "modulus", 2**256)
    if modulus < 1:
        raise ValueError("modulus must be positive")
    family = arguments.get("family", "fibonacci")
    # An independent recurrence implementation, rather than the source example's matrix representation.
    if family == "fibonacci":
        a, b = 0, 1 % modulus
        for bit in bin(n)[2:]:
            c = a * ((2*b-a) % modulus) % modulus
            d = (a*a+b*b) % modulus
            a, b = (c, d) if bit == "0" else (d, (c+d) % modulus)
        value = a
        method = "Fast doubling with exact integer modular arithmetic"
    elif family == "affine":
        coefficient = integer(arguments.get("coefficient", 1664525), "coefficient", 10**30)
        increment = integer(arguments.get("increment", 1013904223), "increment", 10**30)
        seed = integer(arguments.get("seed", 42), "seed", 10**30)
        mul, add, base_mul, base_add, remaining = 1, 0, coefficient % modulus, increment % modulus, n
        while remaining:
            if remaining & 1:
                mul, add = base_mul*mul % modulus, (base_mul*add+base_add) % modulus
            base_mul, base_add = base_mul*base_mul % modulus, (base_mul*base_add+base_add) % modulus
            remaining >>= 1
        value = (mul*seed+add) % modulus
        method = "Composition of exact affine maps by exponentiation by squaring"
    else:
        raise ValueError("Choose fibonacci or affine")
    return {"status": "EXACT_RECURRENCE_RESULT", "evidence_type": "exact_integer_computation", "value": str(value),
            "steps": str(n), "modulus": str(modulus), "family": family, "method": method,
            "explanation": f"Computed the requested {family} state after {n} steps modulo {modulus}.",
            "scope": "This shortcut applies to the selected structured recurrence, not arbitrary computation.",
            "certificate": {"kind": "recurrence_replay", "arguments": arguments, "value": str(value)}}


def check_inequality(arguments):
    bound = arguments.get("bound", "2")
    if not re.fullmatch(r"-?\d{1,8}(/\d{1,8})?", str(bound)):
        raise ValueError("Use an exact rational bound")
    Fraction(str(bound))
    certificate = json.loads((ROOT / "examples/sharp-quadratic-certificate.json").read_text())
    certificate["bound"] = str(bound)
    verdict = verify(certificate)
    return {"status": verdict["status"], "evidence_type": "exact_inequality_certificate", "verification": verdict,
            "certificate": certificate, "formula": "5x² + 6xy + 5y² ≥ λ(x² + y²)",
            "explanation": "At λ=2 the residual is 3(x+y)²; (-1,1) attains equality, so the constant is sharp." if verdict["status"] == "CERTIFIED_SHARP_INEQUALITY" else "The supplied certificate does not prove this bound. Failure of a certificate is not itself a counterexample to the inequality.",
            "domain": "All real x and y. The equality witness has nonzero reference value.",
            "scope": "This tool checks the displayed quadratic control, not arbitrary inequalities."}


def discover_invariant(arguments):
    """Counterexample-guided synthesis with deterministic, replayable budgets."""
    # Use the checker entry point to validate names, syntax and parameter semantics.
    setup = check_invariant({**arguments, "numerator": "1"})
    goal = RationalGoal.from_dict(setup["certificate"]["goal"])
    degree = integer(arguments.get("max_degree", 3), "max_degree", 3)
    budget = integer(arguments.get("max_checks", 16), "max_checks", 32)
    if degree < 1 or budget < 1:
        raise ValueError("Choose degree 1–3 and a check budget of 1–32")
    denominator = A.parse(bounded_expression(arguments.get("denominator", "x*y")), goal.variables)
    if not denominator:
        raise ValueError("The discovery denominator must be nonzero")
    dim = len(goal.variables)
    points, attempts = [], []
    # Sampling proposes coefficients. Only the separate symbolic verifier certifies.
    for j in range(dim):
        for value in (1, -1, 2):
            point = tuple(Fraction(value if i == j else 1) for i in range(dim))
            try:
                image = [m.at(point) for m in goal.maps]
                if A.evaluate(denominator, point) and A.evaluate(denominator, image) and point not in points:
                    points.append(point)
            except ZeroDivisionError:
                pass
    visited = set()
    accepted = None
    for current_degree in range(1, degree + 1):
        basis = R.all_monomials(dim, current_degree)
        while len(attempts) < budget:
            rows = []
            for point in points:
                image = [m.at(point) for m in goal.maps]
                d0, d1 = A.evaluate(denominator, point), A.evaluate(denominator, image)
                rows.append([A.evaluate({m: Fraction(1)}, image)*d0 - A.evaluate({m: Fraction(1)}, point)*d1 for m in basis])
            learned = False
            for vector in A.nullspace(rows, len(basis)):
                numerator = R.primitive({m: c for m, c in zip(basis, vector) if c})
                function = R.Rational.poly(numerator, dim).div(R.Rational.poly(denominator, dim))
                key = canonical(A.terms(numerator))
                if key in visited or not R.depends_on_state(function, goal.parameter_indices):
                    continue
                visited.add(key)
                certificate = goal.certificate(numerator, denominator)
                verdict = verify(certificate)
                attempt = {"numerator": A.format_poly(numerator, goal.variables), "denominator": A.format_poly(denominator, goal.variables), "status": verdict["status"]}
                attempts.append(attempt)
                if verdict["status"] == "CERTIFIED_RATIONAL_INVARIANT":
                    accepted = check_invariant({**arguments, "numerator": attempt["numerator"], "denominator": attempt["denominator"]})
                    break
                if verdict["status"] != "REFUTED":
                    raise ValueError("Discovery stopped: the verifier did not return a usable counterexample")
                attempt["counterexample"] = verdict["counterexample"]
                point = tuple(Fraction(verdict["counterexample"][v]) for v in goal.variables)
                if point in points:
                    raise ValueError("Discovery stopped: repeated counterexample")
                points.append(point)
                learned = True
                break
            if accepted or not learned or len(attempts) >= budget:
                break
        if accepted or len(attempts) >= budget:
            break
    result = accepted or {"status": "NO_RESULT_WITHIN_TEMPLATE", "evidence_type": "bounded_search", "explanation": "No conserved quantity was certified within this numerator degree, fixed denominator and check budget.", "domain": setup["domain"], "scope": "A bounded search failure is inconclusive. It does not prove that no invariant exists."}
    return {**result, "search": {"method": "Counterexample-guided exact linear algebra followed by independent symbolic verification", "max_degree": degree, "max_checks": budget, "denominator": arguments.get("denominator", "x*y"), "checks_used": len(attempts), "attempts": attempts}, "historical_novelty": "UNREVIEWED"}


def trace_orbit(arguments):
    checked = check_invariant(arguments)
    goal = RationalGoal.from_dict(checked["certificate"]["goal"])
    steps = integer(arguments.get("steps", 8), "steps", 24)
    seed = arguments.get("seed", ["1"] * len(goal.variables))
    if not isinstance(seed, list) or len(seed) != len(goal.variables) or any(not isinstance(v, str) or not re.fullmatch(r"-?\d{1,6}(/\d{1,6})?", v) for v in seed):
        raise ValueError("Provide one small exact rational seed per variable")
    point = tuple(Fraction(v) for v in seed)
    quantity = R.parse(f"({bounded_expression(arguments.get('numerator', '(x+1)*(y+1)*(x+y+a)'))})/({bounded_expression(arguments.get('denominator', 'x*y'))})", goal.variables)
    rows, stopped = [], None
    for index in range(steps + 1):
        if any(max(abs(v.numerator).bit_length(), v.denominator.bit_length()) > 512 for v in point):
            stopped = "Exact orbit reached the 512-bit state limit"
            break
        try:
            value = quantity.at(point)
            rows.append({"step": index, "state": {v: str(q) for v, q in zip(goal.variables, point)}, "quantity": str(value)})
            if index < steps:
                point = tuple(m.at(point) for m in goal.maps)
        except ZeroDivisionError:
            stopped = f"Step {index} reaches a singularity outside the expression domain"
            break
    return {"status": "ORBIT_STOPPED" if stopped else "EXACT_ORBIT", "evidence_type": "exact_finite_trace", "explanation": stopped or "Each displayed step and quantity was computed with exact rational arithmetic.", "rows": rows, "variables": goal.variables, "formula": checked["formula"], "domain": checked["domain"], "scope": "A finite orbit illustrates behavior; constant samples alone are not a proof of invariance. Use the symbolic checker for a uniform identity."}


TOOLS = {
    "check_invariant": ("Check a rational recurrence invariant using a separate exact arithmetic kernel.", check_invariant),
    "recurrence_jump": ("Compute a Fibonacci or affine recurrence after a large number of steps with exact modular arithmetic.", recurrence_jump),
    "check_inequality": ("Check the sharp-bound certificate for 5x²+6xy+5y² against x²+y².", check_inequality),
    "discover_invariant": ("Synthesize a rational invariant from recurrence transitions, a fixed denominator and a bounded numerator template. Every accepted result is independently checked.", discover_invariant),
    "trace_orbit": ("Compute a short exact rational orbit to inspect a counterexample or illustrate a checked invariant. Finite traces are not proofs.", trace_orbit),
}


def dispatch(name, arguments):
    if name not in TOOLS or not isinstance(arguments, dict):
        raise ValueError("Unknown tool or invalid tool arguments")
    if len(canonical(arguments)) > 12000:
        raise ValueError("Tool arguments exceed the supported size")
    try:
        return TOOLS[name][1](arguments)
    except RuntimeError as error:
        raise ValueError(f"The exact checker reached a computation limit: {error}") from error


def engine_hashes():
    paths = [Path(__file__), ROOT/"vendor/noetherforge/proofcheck.py", ROOT/"vendor/noetherforge/verifier.py", ROOT/"vendor/noetherforge/rational.py", ROOT/"vendor/noetherforge/algebra.py", ROOT/"vendor/noetherforge/goals.py", ROOT/"examples/sharp-quadratic-certificate.json"]
    # Python and JSON parse CRLF/LF identically. Keep receipts portable across Git checkouts.
    return {str(p.relative_to(ROOT)).replace("\\", "/"): hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest() for p in paths}
