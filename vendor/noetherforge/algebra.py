"""Search-side sparse polynomial arithmetic and exact linear algebra over Q."""

from __future__ import annotations

import ast
import itertools
import math
import time
from fractions import Fraction as Q

MAX_TERMS = 20000
MAX_BITS = 4096


class ResourceLimit(RuntimeError):
    pass


def guard(p):
    if len(p) > MAX_TERMS or any(max(abs(c.numerator).bit_length(), c.denominator.bit_length()) > MAX_BITS for c in p.values()):
        raise ResourceLimit("Exact arithmetic exceeded the declared term or coefficient cap")
    return p


def add(a, b):
    p = dict(a)
    for m, c in b.items():
        p[m] = p.get(m, Q(0)) + c
        if not p[m]:
            del p[m]
    return guard(p)


def scale(a, c):
    return guard({m: v * c for m, v in a.items() if v * c})


def mul(a, b):
    if len(a) * len(b) > 2000000:
        raise ResourceLimit("Polynomial product exceeded the multiplication-work cap")
    p = {}
    for m, c in a.items():
        for n, d in b.items():
            k = tuple(x + y for x, y in zip(m, n))
            p[k] = p.get(k, Q(0)) + c * d
        if len(p) > MAX_TERMS:
            raise ResourceLimit("Polynomial product exceeded the term cap")
    return guard({m: c for m, c in p.items() if c})


def power(p, n, dim):
    r = {(0,) * dim: Q(1)}
    while n:
        if n & 1:
            r = mul(r, p)
        n //= 2
        if n:
            p = mul(p, p)
    return r


def parse(expression, variables):
    if not isinstance(expression, str) or len(expression) > 12000:
        raise ValueError("A polynomial must be a string of at most 12000 characters")
    dim = len(variables)
    zero = (0,) * dim
    tree = ast.parse(expression, mode="eval")
    if sum(1 for _ in ast.walk(tree)) > 1500:
        raise ResourceLimit("Expression exceeded the syntax cap")

    def visit(n):
        if isinstance(n, ast.Constant) and type(n.value) is int:
            return guard({zero: Q(n.value)}) if n.value else {}
        if isinstance(n, ast.Name) and n.id in variables:
            m = [0] * dim
            m[variables.index(n.id)] = 1
            return {tuple(m): Q(1)}
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, (ast.UAdd, ast.USub)):
            return scale(visit(n.operand), Q(-1 if isinstance(n.op, ast.USub) else 1))
        if isinstance(n, ast.BinOp):
            if isinstance(n.op, ast.Pow):
                if not isinstance(n.right, ast.Constant) or type(n.right.value) is not int or not 0 <= n.right.value <= 12:
                    raise ValueError("Exponents must be literal integers from 0 to 12")
                return power(visit(n.left), n.right.value, dim)
            a, b = visit(n.left), visit(n.right)
            if isinstance(n.op, ast.Add):
                return add(a, b)
            if isinstance(n.op, ast.Sub):
                return add(a, scale(b, Q(-1)))
            if isinstance(n.op, ast.Mult):
                return mul(a, b)
            if isinstance(n.op, ast.Div) and len(b) == 1 and zero in b and b[zero]:
                return scale(a, 1 / b[zero])
        raise ValueError("Only polynomial names, integer constants, +, -, *, ** and division by rational constants are allowed")

    return visit(tree.body)


def evaluate(p, values):
    return sum((c * math.prod(v ** k for v, k in zip(values, m)) for m, c in p.items()), Q(0))


def compose(p, maps, dim):
    cache = {}
    result = {}
    for m, c in p.items():
        term = {(0,) * dim: c}
        for i, k in enumerate(m):
            if k:
                if (i, k) not in cache:
                    cache[i, k] = power(maps[i], k, dim)
                term = mul(term, cache[i, k])
        result = add(result, term)
    return result


def monomials(dim, degree, parameters=()):
    """All nonconstant monomials of total degree <= degree, modulo parameter-only terms."""
    params = set(parameters)
    result = []
    for d in range(1, degree + 1):
        for combination in itertools.combinations_with_replacement(range(dim), d):
            m = tuple(combination.count(i) for i in range(dim))
            if any(m[i] and i not in params for i in range(dim)):
                result.append(m)
    return result


def nullspace(rows, width, deadline=None):
    """RREF with exact fractions. Returns a rational basis, including empty-matrix cases."""
    a = [list(map(Q, row)) for row in rows if any(row)]
    pivots = []
    r = 0
    for col in range(width):
        if deadline is not None and time.monotonic() >= deadline:
            raise ResourceLimit("Exact linear solve exceeded the cooperative wall cap")
        pivot = next((j for j in range(r, len(a)) if a[j][col]), None)
        if pivot is None:
            continue
        a[r], a[pivot] = a[pivot], a[r]
        q = a[r][col]
        a[r] = [x / q for x in a[r]]
        for j in range(len(a)):
            if j != r and a[j][col]:
                q = a[j][col]
                a[j] = [x - q * y for x, y in zip(a[j], a[r])]
        if any(max(abs(x.numerator).bit_length(), x.denominator.bit_length()) > MAX_BITS for row in a for x in row):
            raise ResourceLimit("Linear system exceeded the coefficient cap")
        pivots.append(col)
        r += 1
        if r == len(a):
            break
    free = [j for j in range(width) if j not in pivots]
    basis = []
    for col in free:
        v = [Q(0)] * width
        v[col] = Q(1)
        for row, pivot in enumerate(pivots):
            v[pivot] = -a[row][col]
        basis.append(v)
    return basis


def normalize(p):
    """Identify H and a*H+b for nonzero rational a, without conflating other formulas."""
    p = {m: Q(c) for m, c in p.items() if c and any(m)}
    if not p:
        return {}
    denominator = math.lcm(*(c.denominator for c in p.values()))
    values = [int(c * denominator) for c in p.values()]
    divisor = math.gcd(*values)
    first = min(p, key=lambda m: (sum(m), tuple(-k for k in m)))
    sign = 1 if p[first] > 0 else -1
    return {m: Q(int(c * denominator) // divisor * sign) for m, c in p.items()}


def terms(p):
    return [{"powers": list(m), "coefficient": str(c)} for m, c in sorted(p.items(), key=lambda item: (sum(item[0]), item[0])) if c]


def format_poly(p, variables, lean=False):
    parts = []
    for m, c in sorted(p.items(), key=lambda item: (sum(item[0]), item[0])):
        factors = [f"({c.numerator} : ℚ)" if lean else str(c.numerator)]
        if c.denominator != 1:
            factors[0] = f"({factors[0]} / {c.denominator})" if lean else str(c)
        for name, k in zip(variables, m):
            if k:
                factors.append(name if k == 1 else f"({name} ^ {k})" if lean else f"{name}**{k}")
        parts.append(" * ".join(factors))
    return " + ".join(parts) or "0"
