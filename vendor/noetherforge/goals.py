"""Typed problem contracts; parsing never executes a supplied expression."""

from __future__ import annotations

import hashlib
import json
import keyword
import re
from dataclasses import dataclass

from .algebra import monomials, parse, terms


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()


@dataclass
class Goal:
    id: str
    variables: list[str]
    transitions: list[str]
    max_degree: int = 4
    parameters: tuple[str, ...] = ()
    sources: tuple[str, ...] = ()

    def __post_init__(self):
        if not re.fullmatch(r"[a-zA-Z0-9_-]{1,100}", self.id):
            raise ValueError("Goal id must be a short alphanumeric identifier")
        if not 1 <= len(self.variables) <= 5 or len(set(self.variables)) != len(self.variables):
            raise ValueError("Use one to five distinct variables")
        if any(not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,30}", v) or keyword.iskeyword(v) for v in self.variables):
            raise ValueError("Invalid variable name")
        if len(self.transitions) != len(self.variables):
            raise ValueError("One transition is required for every variable")
        if type(self.max_degree) is not int or not 1 <= self.max_degree <= 8:
            raise ValueError("Degree must be an integer from one to eight")
        if len(set(self.parameters)) != len(self.parameters) or not set(self.parameters) < set(self.variables):
            raise ValueError("Parameters must be a proper subset of the variables")
        self.maps = [parse(e, self.variables) for e in self.transitions]
        for name in self.parameters:
            if self.maps[self.variables.index(name)] != parse(name, self.variables):
                raise ValueError("A parameter must be fixed by the transition")
        if len(monomials(len(self.variables), self.max_degree, self.parameter_indices)) > 180:
            raise ValueError("The candidate template exceeds 180 coefficients")

    @property
    def parameter_indices(self):
        return tuple(self.variables.index(p) for p in self.parameters)

    @property
    def map_hash(self):
        return digest({"domain": "QQ", "variables": self.variables, "parameters": list(self.parameters), "maps": [terms(m) for m in self.maps]})

    def as_dict(self):
        return {"id": self.id, "variables": self.variables, "transitions": self.transitions, "max_degree": self.max_degree, "parameters": list(self.parameters), "sources": list(self.sources)}

    @classmethod
    def from_dict(cls, data):
        return cls(data["id"], list(data["variables"]), list(data["transitions"]), data.get("max_degree", 4), tuple(data.get("parameters", [])), tuple(data.get("sources", [])))

    def certificate(self, polynomial):
        return {"schema_version": 1, "kind": "polynomial_invariant", "domain": "QQ", "goal": self.as_dict(), "map_hash": self.map_hash, "candidate": terms(polynomial), "proof_obligation": "H(T(x)) - H(x) is the zero polynomial over QQ"}
