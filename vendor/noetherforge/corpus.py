"""Search the pinned release with source hashes, line pointers and explicit trust labels."""

from __future__ import annotations

import hashlib
import html
import json
import math
import re
from collections import Counter
from pathlib import Path

from .goals import digest

UPSTREAM_COMMIT = "adc7f1241b42e322a6451854ab7e4b4c146bf78a"
STOPWORDS = {"a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "in", "is", "of", "on", "or", "that", "the", "to", "we", "with", "it", "this", "its"}


def tokens(text):
    return [w.lower() for w in re.findall(r"[A-Za-z][A-Za-z0-9-]{1,}", text) if w.lower() not in STOPWORDS]


def clean(text):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]*>", " ", text))).strip()


def build_index(root):
    root = Path(root)
    source = root / "CONTENTS.md"
    raw = source.read_bytes()
    text = raw.decode("utf-8")
    headings = list(re.finditer(r"^\*\*(\d{3})\. (.*?)\*\*", text, re.M))
    rows = []
    for i, match in enumerate(headings):
        end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
        section = text[match.start():end]
        family = match.group(1)
        doc = root / "lean" / "docs" / f"{family}.md"
        formalization = None
        if doc.is_file():
            contents = doc.read_text(encoding="utf-8")
            formalization = {"path": doc.relative_to(root).as_posix(), "sha256": hashlib.sha256(doc.read_bytes()).hexdigest(), "description": contents[:12000], "status": "UPSTREAM_DOCUMENTATION_NOT_LOCALLY_VERIFIED"}
        papers = [{"title": clean(m.group(1)), "path": m.group(2)} for m in re.finditer(r"\[([^\n]+?)\]\((preprints/[^)]+\.pdf)\)", section)]
        line = text.count("\n", 0, match.start()) + 1
        rows.append({"family": family, "title": clean(match.group(2)), "text": clean(section), "line": line, "papers": papers, "formalization": formalization, "status": "UPSTREAM_CLAIM_NOT_LOCALLY_VERIFIED", "source_url": f"https://github.com/openai/math/blob/{UPSTREAM_COMMIT}/CONTENTS.md#L{line}"})
    if not rows:
        raise ValueError("No manuscript families were parsed from CONTENTS.md")
    claim = re.search(r"\*\*(\d+) manuscripts covering (\d+) result families",text)
    indexed = sum(len(r["papers"]) for r in rows)
    result = {"schema_version": 1, "upstream_repository": "https://github.com/openai/math", "upstream_commit": UPSTREAM_COMMIT, "source": "CONTENTS.md", "source_sha256": hashlib.sha256(raw).hexdigest(), "families": rows, "counts": {"families": len(rows), "indexed_manuscript_links": indexed, "claimed_manuscripts": int(claim.group(1)) if claim else None, "families_with_formalization_documentation": sum(r["formalization"] is not None for r in rows)}, "catalogue_warning": "The upstream header claims 722 manuscripts; the pinned map contains 721 matching manuscript PDF links" if claim and int(claim.group(1)) != indexed else None}
    result["index_hash"] = digest(result)
    return result


def query(index, phrase, limit=5):
    """BM25 over families. Retrieval similarity is not a novelty proof."""
    docs = [Counter(tokens(" ".join([r["title"]] * 3) + " " + r["text"])) for r in index["families"]]
    average = sum(map(lambda d: sum(d.values()), docs)) / len(docs)
    terms = sorted(set(tokens(phrase)))
    n = len(docs)
    df = {t: sum(t in d for d in docs) for t in terms}
    ranked = []
    for row, doc in zip(index["families"], docs):
        score = 0.0
        length = sum(doc.values())
        for term in terms:
            f = doc[term]
            if f:
                idf = math.log(1 + (n - df[term] + .5) / (df[term] + .5))
                score += idf * f * 2.2 / (f + 1.2 * (.25 + .75 * length / average))
        if score:
            ranked.append({**row, "retrieval_score": score})
    ranked.sort(key=lambda r: (-r["retrieval_score"], r["family"]))
    return ranked[:limit]


def packet(index, question, limit=5):
    sources = query(index, question, limit)
    return {"schema_version": 1, "question": question, "corpus_commit": index["upstream_commit"], "corpus_hash": index["index_hash"], "source_status": "Related upstream claims are context, not established lemmas until checked", "sources": sources, "routes": [{"mechanism": "generalize", "instruction": "State exact quantifiers and assumptions. Change one dimension, parameter regime, or hypothesis in a retrieved result. Identify the first unproved implication and its cheapest discriminating check."}, {"mechanism": "transfer", "instruction": "Write an explicit dictionary between two retrieved structures. Propose a precise lemma in the target domain. Check the dictionary before using any conclusion."}, {"mechanism": "falsify", "instruction": "Search boundary and degenerate cases of the same statement. Return an exact counterexample or the tested finite domain. Finite success is not a universal proof."}], "proposal_contract": {"goal": {"id": "your-goal", "variables": ["x", "y"], "transitions": ["polynomial in x,y", "polynomial in x,y"], "parameters": [], "max_degree": 4, "sources": [s["source_url"] for s in sources]}, "invariant": "optional polynomial to check; omit to invoke synthesis", "mathematical_motivation": "Explain how this problem advances the original objective", "historical_novelty": "UNREVIEWED"}, "review_obligations": ["Check original references and closest prior results beyond this corpus", "Independently check the exact theorem and dependencies", "Compare scope, hypotheses, sharpness, and computational cost with a fixed baseline", "Report unsuccessful attempts and actual resource use"]}


def save_index(root, path):
    result = build_index(root)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    return result
