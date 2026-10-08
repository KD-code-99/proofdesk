"""Search-side exact rational functions with syntax-preserving domain guards."""

from __future__ import annotations

import ast
import itertools
import json
import math
import re
import time
from dataclasses import dataclass
from fractions import Fraction as Q

from . import algebra as A
from .goals import digest


def primitive(p):
    """Normalize scale, retaining the constant term (unlike invariant normalization)."""
    p = {m:Q(c) for m,c in p.items() if c}
    if not p:
        return {}
    lcm = math.lcm(*(c.denominator for c in p.values()))
    integers = [int(c*lcm) for c in p.values()]
    gcd = abs(math.gcd(*integers))
    first = min(p)
    sign = 1 if p[first]>0 else -1
    return {m:Q(int(c*lcm)//gcd*sign) for m,c in p.items()}


def unique_guards(guards):
    result = {}
    for g in guards:
        if not g:
            raise ValueError("A rational expression has an empty domain")
        if any(any(m) for m in g):
            g = primitive(g)
            result[json.dumps(A.terms(g),sort_keys=True)] = g
    return [result[k] for k in sorted(result)]


@dataclass
class Rational:
    n: dict
    d: dict
    dim: int
    guards: list

    def __post_init__(self):
        if not self.d:
            raise ValueError("Zero rational denominator")
        self.n,self.d = A.guard(self.n),A.guard(self.d)
        self.guards = unique_guards(self.guards)
        # Cancel only common monomial factors. Original domain guards remain.
        if self.n:
            min_n = [min(m[i] for m in self.n) for i in range(self.dim)]
            min_d = [min(m[i] for m in self.d) for i in range(self.dim)]
            common = [min(a,b) for a,b in zip(min_n,min_d)]
            self.n = {tuple(k-j for k,j in zip(m,common)):c for m,c in self.n.items()}
            self.d = {tuple(k-j for k,j in zip(m,common)):c for m,c in self.d.items()}
            lead = self.d[min(self.d)]
            self.n,self.d = A.scale(self.n,1/lead),A.scale(self.d,1/lead)
        else:
            self.d = {(0,)*self.dim:Q(1)}

    @classmethod
    def poly(cls,p,dim,guards=()):
        return cls(p,{(0,)*dim:Q(1)},dim,list(guards))

    def add(self,other):
        return Rational(A.add(A.mul(self.n,other.d),A.mul(other.n,self.d)),A.mul(self.d,other.d),self.dim,self.guards+other.guards)

    def neg(self):
        return Rational(A.scale(self.n,Q(-1)),self.d,self.dim,self.guards)

    def sub(self,other):
        return self.add(other.neg())

    def mul(self,other):
        return Rational(A.mul(self.n,other.n),A.mul(self.d,other.d),self.dim,self.guards+other.guards)

    def div(self,other):
        if not other.n:
            raise ValueError("Division by an identically zero rational function")
        return Rational(A.mul(self.n,other.d),A.mul(self.d,other.n),self.dim,self.guards+other.guards+[other.n])

    def pow(self,k):
        if k<0:
            return Rational.poly({(0,)*self.dim:Q(1)},self.dim).div(self.pow(-k))
        return Rational(A.power(self.n,k,self.dim),A.power(self.d,k,self.dim),self.dim,self.guards)

    def at(self,point):
        if any(not A.evaluate(g,point) for g in self.guards):
            raise ZeroDivisionError("Point is outside the original rational-expression domain")
        d = A.evaluate(self.d,point)
        if not d:
            raise ZeroDivisionError("Point is outside the rational domain")
        return A.evaluate(self.n,point)/d


def parse(expression,names):
    if not isinstance(expression,str) or len(expression)>12000:
        raise ValueError("Invalid rational expression")
    tree = ast.parse(expression,mode='eval')
    if sum(1 for _ in ast.walk(tree))>1500:
        raise A.ResourceLimit("Rational syntax cap")
    dim = len(names)

    def walk(node):
        if isinstance(node,ast.Constant) and type(node.value) is int:
            return Rational.poly({(0,)*dim:Q(node.value)} if node.value else {},dim)
        if isinstance(node,ast.Name) and node.id in names:
            m = tuple(int(i==names.index(node.id)) for i in range(dim))
            return Rational.poly({m:Q(1)},dim)
        if isinstance(node,ast.UnaryOp) and isinstance(node.op,(ast.USub,ast.UAdd)):
            p = walk(node.operand)
            return p.neg() if isinstance(node.op,ast.USub) else p
        if isinstance(node,ast.BinOp):
            if isinstance(node.op,ast.Pow):
                power = node.right
                sign = 1
                if isinstance(power,ast.UnaryOp) and isinstance(power.op,ast.USub):
                    power,sign = power.operand,-1
                if not isinstance(power,ast.Constant) or type(power.value) is not int or not 0<=power.value<=8:
                    raise ValueError("Rational exponents must be literal integers between -8 and 8")
                return walk(node.left).pow(sign*power.value)
            a,b = walk(node.left),walk(node.right)
            if isinstance(node.op,ast.Add): return a.add(b)
            if isinstance(node.op,ast.Sub): return a.sub(b)
            if isinstance(node.op,ast.Mult): return a.mul(b)
            if isinstance(node.op,ast.Div): return a.div(b)
        raise ValueError("Unsupported rational expression")

    return walk(tree.body)


def substitute_poly(p,maps,dim):
    out = Rational.poly({},dim)
    for m,c in p.items():
        term = Rational.poly({(0,)*dim:c},dim)
        for i,k in enumerate(m):
            if k:
                term = term.mul(maps[i].pow(k))
        out = out.add(term)
    return out


def depends_on_state(p,parameters):
    for i in range(p.dim):
        if i in parameters:
            continue
        def derivative(poly):
            out = {}
            for m,c in poly.items():
                if m[i]:
                    n = list(m); n[i]-=1
                    out[tuple(n)] = c*m[i]
            return out
        if A.add(A.mul(derivative(p.n),p.d),A.scale(A.mul(p.n,derivative(p.d)),Q(-1))):
            return True
    return False


def domain_of_identity(goal,numerator,denominator):
    dim = len(goal.variables)
    invariant = Rational.poly(numerator,dim).div(Rational.poly(denominator,dim))
    after = substitute_poly(numerator,goal.maps,dim).div(substitute_poly(denominator,goal.maps,dim))
    guards = unique_guards([g for m in goal.maps for g in m.guards]+goal.explicit_guards+invariant.guards+after.guards)
    return invariant,after,guards


@dataclass
class RationalGoal:
    id: str
    variables: list[str]
    transitions: list[str]
    max_degree: int = 4
    max_denominator_degree: int = 2
    parameters: tuple[str,...] = ()
    guards: tuple[str,...] = ()
    sources: tuple[str,...] = ()

    def __post_init__(self):
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}',self.id):
            raise ValueError("Invalid rational goal id")
        if not 1<=len(self.variables)<=4 or len(set(self.variables))!=len(self.variables) or any(not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,30}',v) for v in self.variables):
            raise ValueError("Use one to four valid distinct rational variables")
        if len(self.transitions)!=len(self.variables) or not set(self.parameters)<set(self.variables):
            raise ValueError("Invalid transition or parameter set")
        if type(self.max_degree) is not int or not 1<=self.max_degree<=6 or type(self.max_denominator_degree) is not int or not 0<=self.max_denominator_degree<=3:
            raise ValueError("Invalid rational template bounds")
        self.maps = [parse(s,self.variables) for s in self.transitions]
        self.explicit_guards = unique_guards([A.parse(g,self.variables) for g in self.guards])
        for name in self.parameters:
            i = self.variables.index(name)
            if self.maps[i].sub(parse(name,self.variables)).n:
                raise ValueError("A symbolic parameter changes under the recurrence")
        if len(all_monomials(len(self.variables),self.max_degree))>180:
            raise ValueError("Rational numerator template exceeds 180 coefficients")

    @property
    def parameter_indices(self):
        return tuple(self.variables.index(p) for p in self.parameters)

    def as_dict(self):
        return {'id':self.id,'kind':'rational_recurrence','variables':self.variables,'transitions':self.transitions,'max_degree':self.max_degree,'max_denominator_degree':self.max_denominator_degree,'parameters':list(self.parameters),'guards':list(self.guards),'sources':list(self.sources)}

    @property
    def map_hash(self):
        return digest({'kind':'rational_recurrence','variables':self.variables,'transitions':self.transitions,'parameters':list(self.parameters),'guards':list(self.guards)})

    @classmethod
    def from_dict(cls,data):
        return cls(data['id'],list(data['variables']),list(data['transitions']),data.get('max_degree',4),data.get('max_denominator_degree',2),tuple(data.get('parameters',[])),tuple(data.get('guards',[])),tuple(data.get('sources',[])))

    def certificate(self,n,d):
        _,_,guards = domain_of_identity(self,n,d)
        return {'schema_version':2,'kind':'rational_invariant','domain':'QQ','goal':self.as_dict(),'map_hash':self.map_hash,'numerator':A.terms(n),'denominator':A.terms(d),'required_nonzero_guards':[A.terms(g) for g in guards],'historical_novelty':'UNREVIEWED'}


def all_monomials(dim,degree):
    return [(0,)*dim]+A.monomials(dim,degree)


def denominator_schedule(goal):
    dim = len(goal.variables)
    zero = (0,)*dim
    yield {zero:Q(1)}
    active = [i for i in range(dim) if i not in goal.parameter_indices]
    for degree in range(1,goal.max_denominator_degree+1):
        for word in itertools.combinations_with_replacement(active,degree):
            yield {tuple(word.count(i) for i in range(dim)):Q(1)}


def discover(goal,budget=200,seconds=90):
    from .proofcheck import verify

    if not 1<=budget<=2000 or not 0<seconds<=3600:
        raise ValueError("Invalid rational discovery budget")
    started = time.monotonic(); deadline = started+seconds
    proposals,accepted,checks,solves = [],[],0,0
    dim = len(goal.variables)
    seed = [tuple(Q(1) for _ in range(dim))]+[tuple(Q(v if i==j else 1) for i in range(dim)) for j in range(dim) for v in (-1,0,2)]
    status = 'NO_RESULT_WITHIN_DECLARED_SEARCH'
    visited = set()
    try:
        for denominator in denominator_schedule(goal):
            points = []
            den_after = substitute_poly(denominator,goal.maps,dim)
            def admissible(pt):
                try:
                    image = [m.at(pt) for m in goal.maps]
                    return all(A.evaluate(g,pt) for g in goal.explicit_guards) and bool(A.evaluate(denominator,pt)) and bool(A.evaluate(denominator,image))
                except ZeroDivisionError:
                    return False
            points = [p for p in seed if admissible(p)]
            for degree in range(1,goal.max_degree+1):
                basis = all_monomials(dim,degree)
                while checks<budget and time.monotonic()<deadline:
                    rows = []
                    for pt in points:
                        image = [m.at(pt) for m in goal.maps]
                        d0,d1 = A.evaluate(denominator,pt),A.evaluate(denominator,image)
                        rows.append([A.evaluate({m:Q(1)},image)*d0-A.evaluate({m:Q(1)},pt)*d1 for m in basis])
                    vectors = A.nullspace(rows,len(basis),deadline=deadline); solves+=1
                    if not vectors: break
                    learned = False
                    polynomials = [{m:c for m,c in zip(basis,v) if c} for v in vectors]
                    polynomials.sort(key=lambda p:(max(map(sum,p),default=0),len(p),json.dumps(A.terms(p),sort_keys=True)))
                    for n in polynomials:
                        function = Rational.poly(n,dim).div(Rational.poly(denominator,dim))
                        if not depends_on_state(function,goal.parameter_indices): continue
                        n = primitive(n)
                        key = digest({'n':A.terms(n),'d':A.terms(denominator)})
                        if key in visited: continue
                        visited.add(key)
                        if checks>=budget or time.monotonic()>=deadline: break
                        cert = goal.certificate(n,denominator)
                        evidence = verify(cert); checks+=1
                        proposals.append({'check':checks,'numerator_degree':degree,'certificate':cert,'verification':evidence})
                        if evidence['status']=='CERTIFIED_RATIONAL_INVARIANT':
                            accepted.append({'certificate':cert,'verification':evidence,'formula':f"({A.format_poly(n,goal.variables)}) / ({A.format_poly(denominator,goal.variables)})"})
                            status='CERTIFIED_RATIONAL_INVARIANT'; break
                        if evidence['status']!='REFUTED':
                            raise ValueError("Unexpected rational verifier verdict")
                        pt = tuple(Q(evidence['counterexample'][v]) for v in goal.variables)
                        if not admissible(pt) or pt in points:
                            raise AssertionError("Rational counterexample violates the search contract")
                        points.append(pt); learned=True; break
                    if accepted or not learned: break
                if accepted or checks>=budget or time.monotonic()>=deadline: break
            if accepted or checks>=budget or time.monotonic()>=deadline: break
        if not accepted and checks>=budget: status='BUDGET_EXHAUSTED'
        elif not accepted and time.monotonic()>=deadline: status='TIME_LIMIT'
    except A.ResourceLimit as error:
        status='RESOURCE_LIMIT'; proposals.append({'status':status,'reason':str(error)})
    return {'schema_version':2,'goal':goal.as_dict(),'map_hash':goal.map_hash,'status':status,'accepted':accepted,'events':proposals,'metrics':{'certificate_checks':checks,'linear_solves':solves,'runtime_seconds':time.monotonic()-started},'budget':{'certificate_checks':budget,'cooperative_wall_seconds':seconds},'scope':'Failure within this numerator and monomial-denominator schedule is inconclusive; it does not establish nonintegrability.'}
