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


TOOLS = {
    "check_invariant": ("Check a rational recurrence invariant using a separate exact arithmetic kernel.", check_invariant),
    "recurrence_jump": ("Compute a Fibonacci or affine recurrence after a large number of steps with exact modular arithmetic.", recurrence_jump),
    "check_inequality": ("Check the sharp-bound certificate for 5x²+6xy+5y² against x²+y².", check_inequality),
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
    paths = [Path(__file__), ROOT/"vendor/noetherforge/proofcheck.py", ROOT/"vendor/noetherforge/verifier.py", ROOT/"vendor/noetherforge/rational.py", ROOT/"vendor/noetherforge/algebra.py", ROOT/"examples/sharp-quadratic-certificate.json"]
    return {str(p.relative_to(ROOT)).replace("\\", "/"): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
