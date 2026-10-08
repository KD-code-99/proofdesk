"""Independent proof checker. Does NOT import the search arithmetic or linear solver.

Monomials are sorted WORDS of variable indices here, instead of exponent vectors.
Identities are decided by distributive expansion with exact rational coefficients.
The checker rebuilds the claimed statement; no supplied success flag is trusted.
"""

from __future__ import annotations

import ast
import hashlib
import itertools
import json
import math
import re
from collections import defaultdict
from fractions import Fraction

TERM_CAP = 20000
BIT_CAP = 4096


class VerificationLimit(RuntimeError):
    pass


def trim(poly):
    p = {w: c for w, c in poly.items() if c}
    if len(p) > TERM_CAP or any(max(abs(c.numerator).bit_length(), c.denominator.bit_length()) > BIT_CAP for c in p.values()):
        raise VerificationLimit("Independent expansion exceeded its exact arithmetic cap")
    return p


def product(left, right):
    if len(left) * len(right) > 2000000:
        raise VerificationLimit("Independent expansion exceeded its multiplication-work cap")
    out = defaultdict(Fraction)
    for u, a in left.items():
        for v, b in right.items():
            out[tuple(sorted(u + v))] += a * b
        if len(out) > TERM_CAP:
            raise VerificationLimit("Independent expansion exceeded its term cap")
    return trim(out)


def plus(left, right, sign=1):
    out = defaultdict(Fraction, left)
    for w, c in right.items():
        out[w] += sign * c
    return trim(out)


def expand(expression, names):
    if not isinstance(expression, str) or len(expression) > 12000:
        raise ValueError("Invalid polynomial expression")
    node = ast.parse(expression, mode="eval")
    if sum(1 for _ in ast.walk(node)) > 1500:
        raise VerificationLimit("Expression syntax cap")

    def walk(n):
        if isinstance(n, ast.Constant) and type(n.value) is int:
            return trim({(): Fraction(n.value)})
        if isinstance(n, ast.Name) and n.id in names:
            return {(names.index(n.id),): Fraction(1)}
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, (ast.USub, ast.UAdd)):
            return {w: (-c if isinstance(n.op, ast.USub) else c) for w, c in walk(n.operand).items()}
        if isinstance(n, ast.BinOp):
            if isinstance(n.op, ast.Pow):
                if not isinstance(n.right, ast.Constant) or type(n.right.value) is not int or not 0 <= n.right.value <= 12:
                    raise ValueError("Invalid exponent")
                base, out = walk(n.left), {(): Fraction(1)}
                for _ in range(n.right.value):
                    out = product(out, base)
                return out
            left, right = walk(n.left), walk(n.right)
            if isinstance(n.op, ast.Add):
                return plus(left, right)
            if isinstance(n.op, ast.Sub):
                return plus(left, right, -1)
            if isinstance(n.op, ast.Mult):
                return product(left, right)
            if isinstance(n.op, ast.Div) and set(right) == {()} and right[()]:
                return trim({w: c / right[()] for w, c in left.items()})
        raise ValueError("Unsupported expression in certificate")

    return walk(node.body)


def value(poly, point):
    return sum((c * math.prod(point[i] for i in w) for w, c in poly.items()), Fraction(0))


def witness(poly, dim):
    """A nonzero polynomial has a nonzero specialization on a bounded integer grid.

Choose each coordinate while retaining a nonzero restricted polynomial. This is
constructive, not random testing and not an exhaustive exponential grid scan.
"""
    current, point = dict(poly), []
    for i in range(dim):
        degree = max((w.count(i) for w in current), default=0)
        for a in range(degree + 1):
            specialized = defaultdict(Fraction)
            for w, c in current.items():
                specialized[tuple(j for j in w if j != i)] += c * a ** w.count(i)
            specialized = trim(specialized)
            if specialized:
                current = specialized
                point.append(a)
                break
        else:
            raise AssertionError("Nonzero polynomial specialization failed")
    if not value(poly, point):
        raise AssertionError("Invalid counterexample")
    return point


def context(cert):
    if cert.get("schema_version") != 1 or cert.get("domain") != "QQ":
        raise ValueError("Unsupported certificate schema or arithmetic domain")
    goal = cert["goal"]
    names = goal["variables"]
    if not isinstance(names, list) or not 1 <= len(names) <= 5 or len(set(names)) != len(names) or any(not isinstance(v, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,30}", v) for v in names):
        raise ValueError("Invalid variables")
    transitions = goal["transitions"]
    if len(transitions) != len(names):
        raise ValueError("Wrong number of transitions")
    params = goal.get("parameters", [])
    if len(set(params)) != len(params) or not set(params) < set(names):
        raise ValueError("Invalid parameter set")
    maps = [expand(e, names) for e in transitions]
    for name in params:
        if maps[names.index(name)] != {(names.index(name),): Fraction(1)}:
            raise ValueError("Claimed parameter changes under the map")
    canonical_maps = []
    for poly in maps:
        ts = [{"powers": [w.count(i) for i in range(len(names))], "coefficient": str(c)} for w, c in poly.items()]
        canonical_maps.append(sorted(ts, key=lambda t: (sum(t["powers"]), t["powers"])))
    payload = {"domain": "QQ", "variables": names, "parameters": params, "maps": canonical_maps}
    h = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()
    if h != cert["map_hash"]:
        raise ValueError("Certificate is bound to a different transition map")
    return goal, names, maps, {names.index(p) for p in params}


def candidate_terms(ts, dim):
    if not isinstance(ts, list) or not 1 <= len(ts) <= TERM_CAP:
        raise ValueError("Invalid candidate term list")
    out = {}
    for term in ts:
        powers = term["powers"]
        if not isinstance(powers, list) or len(powers) != dim or any(type(k) is not int or not 0 <= k <= 12 for k in powers):
            raise ValueError("Invalid monomial")
        c = term["coefficient"]
        if not isinstance(c, str) or not re.fullmatch(r"-?\d{1,1250}(/\d{1,1250})?", c):
            raise ValueError("Coefficient must be an exact rational string")
        coefficient = Fraction(c)
        word = tuple(i for i, k in enumerate(powers) for _ in range(k))
        if word in out or not coefficient:
            raise ValueError("Duplicate or zero certificate term")
        out[word] = coefficient
    return trim(out)


def check_identity(cert):
    _, names, maps, params = context(cert)
    p = candidate_terms(cert["candidate"], len(names))
    if not any(any(i not in params for i in w) for w in p):
        raise ValueError("An invariant must depend on a state variable")
    composed = {}
    for w, c in p.items():
        term = {(): c}
        for i in w:
            term = product(term, maps[i])
        composed = plus(composed, term)
    residual = plus(composed, p, -1)
    if not residual:
        return {"status": "CERTIFIED_POLYNOMIAL_IDENTITY", "arithmetic": "exact_rational", "residual_terms": 0, "historical_novelty": "UNREVIEWED", "lean_status": "NOT_RUN"}
    pt = witness(residual, len(names))
    image = [value(m, pt) for m in maps]
    before, after = value(p, pt), value(p, image)
    if before == after:
        raise AssertionError("Expanded and direct counterexample evaluations disagree")
    return {"status": "REFUTED", "counterexample": {n: str(v) for n, v in zip(names, pt)}, "before": str(before), "after": str(after), "residual_terms": len(residual)}


def modular_rank(matrix, prime):
    """Independent Gaussian elimination in a prime field, not search-side Q RREF."""
    a = [[int(c.numerator % prime) * pow(int(c.denominator % prime), -1, prime) % prime for c in row] for row in matrix]
    rank = 0
    if not a:
        return 0
    for j in range(len(a[0])):
        r = next((i for i in range(rank, len(a)) if a[i][j]), None)
        if r is None:
            continue
        a[rank], a[r] = a[r], a[rank]
        inv = pow(a[rank][j], -1, prime)
        for i in range(rank + 1, len(a)):
            factor = a[i][j] * inv % prime
            if factor:
                a[i] = [(u - factor * v) % prime for u, v in zip(a[i], a[rank])]
        rank += 1
        if rank == len(a):
            break
    return rank


def check_exclusion(cert):
    goal, names, maps, params = context(cert)
    degree = cert["max_degree"]
    if type(degree) is not int or not 1 <= degree <= 8:
        raise ValueError("Invalid exclusion degree")
    words = [w for d in range(1, degree + 1) for w in itertools.combinations_with_replacement(range(len(names)), d) if any(i not in params for i in w)]
    if len(words) > 180 or len(cert["points"]) > 500:
        raise VerificationLimit("Exclusion template cap")
    rows = []
    for point in cert["points"]:
        if len(point) != len(names):
            raise ValueError("Invalid exclusion point")
        if any(not isinstance(c, str) or not re.fullmatch(r"-?\d{1,1250}(/\d{1,1250})?", c) for c in point):
            raise ValueError("Invalid exact point")
        pt = [Fraction(c) for c in point]
        image = [value(m, pt) for m in maps]
        rows.append([math.prod(image[i] for i in w) - math.prod(pt[i] for i in w) for w in words])
    for prime in (2147483647, 1000000007, 1000000009):
        try:
            rank = modular_rank(rows, prime)
        except ValueError:
            continue
        if rank == len(words):
            return {"status": "CERTIFIED_TEMPLATE_EXCLUSION", "max_degree": degree, "columns": len(words), "rank": rank, "prime": prime, "scope": "No invariant depending on state variables in the entire polynomial template of this degree, modulo parameter-only polynomials"}
    return {"status": "INCONCLUSIVE", "reason": "Independent modular full-rank certificate was not obtained"}


def verify(cert):
    if cert.get("kind") == "polynomial_invariant":
        return check_identity(cert)
    if cert.get("kind") == "template_exclusion":
        return check_exclusion(cert)
    if cert.get("kind") == "symbolic_template_exclusion":
        _,names,maps,params = context(cert)
        degree = cert["max_degree"]
        if type(degree) is not int or not 1 <= degree <= 8:
            raise ValueError("Invalid symbolic exclusion degree")
        words = [w for d in range(1,degree+1) for w in itertools.combinations_with_replacement(range(len(names)),d) if any(i not in params for i in w)]
        if len(words)>180:
            raise VerificationLimit("Symbolic exclusion template cap")
        columns = []
        for w in words:
            image = {():Fraction(1)}
            for i in w:
                image = product(image,maps[i])
            columns.append(plus(image,{w:Fraction(-1)}))
        support = sorted(set().union(*(set(c) for c in columns)))
        matrix = [[column.get(w,Fraction(0)) for column in columns] for w in support]
        for prime in (2147483647,1000000007,1000000009):
            try:
                rank = modular_rank(matrix,prime)
            except ValueError:
                continue
            if rank == len(words):
                return {"status":"CERTIFIED_TEMPLATE_EXCLUSION","max_degree":degree,"columns":len(words),"rank":rank,"prime":prime,"scope":"Exact symbolic coefficient system has full column rank in the bounded polynomial template"}
        return {"status":"INCONCLUSIVE","reason":"No modular full-rank proof for the symbolic coefficient system"}
    if cert.get("kind") == "invariant_consequence":
        target, known = cert["target"], cert["known"]
        if check_identity(target)["status"] != "CERTIFIED_POLYNOMIAL_IDENTITY" or check_identity(known)["status"] != "CERTIFIED_POLYNOMIAL_IDENTITY":
            raise ValueError("Both consequence statements must independently verify")
        if target["map_hash"] != known["map_hash"]:
            raise ValueError("Consequence statements use different maps")
        dim = len(target["goal"]["variables"])
        p, h = candidate_terms(target["candidate"], dim), candidate_terms(known["candidate"], dim)
        coefficients = cert["coefficients"]
        if not 1 <= len(coefficients) <= 12 or any(not isinstance(c,str) or not re.fullmatch(r"-?\d{1,1250}(/\d{1,1250})?", c) for c in coefficients):
            raise ValueError("Invalid consequence coefficients")
        result, power = {}, {(): Fraction(1)}
        for c in coefficients:
            power = product(power,h)
            result = plus(result,{w: Fraction(c)*a for w,a in power.items()})
        return {"status": "CERTIFIED_POLYNOMIAL_CONSEQUENCE" if not plus(result,p,-1) else "REFUTED"}
    raise ValueError("Unknown proof obligation")


if __name__ == "__main__":
    import sys
    from pathlib import Path
    try:
        certificate = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
        result = verify(certificate)
        print(json.dumps(result,indent=2))
        raise SystemExit(0 if result["status"].startswith("CERTIFIED_") else 2)
    except (ValueError,KeyError,OSError,VerificationLimit) as error:
        print(json.dumps({"status":"INVALID_OR_INCONCLUSIVE","reason":str(error)}))
        raise SystemExit(1)
