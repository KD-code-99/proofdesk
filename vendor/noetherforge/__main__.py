"""Run from repository root: python -B -m noetherforge --help."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .algebra import parse
from .benchmark import run_benchmark
from .corpus import packet, query, save_index
from .engine import Archive, inspect_candidate, replay, search, write_run
from .evolution import evolve, export_lean
from .goals import Goal
from .proofcheck import verify

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def emit(value):
    print(json.dumps(value, indent=2, ensure_ascii=sys.stdout.encoding.lower() == "ascii"))


def main(argv=None):
    parser = argparse.ArgumentParser(description="NOETHER-FORGE: proof-carrying mathematical invention")
    subs = parser.add_subparsers(dest="command", required=True)
    p = subs.add_parser("index", help="Index the pinned mathematical corpus")
    p.add_argument("--root", type=Path, default=ROOT / 'vendor/openai-math')
    p.add_argument("--out", type=Path, default=ROOT / ".noetherforge/corpus.json")
    for name in ("search", "prepare"):
        p = subs.add_parser(name, help="Retrieve sources" if name == "search" else "Prepare a source-linked research packet")
        p.add_argument("question")
        p.add_argument("--index", type=Path, default=ROOT / ".noetherforge/corpus.json")
        p.add_argument("--limit", type=int, default=5)
        p.add_argument("--out", type=Path)
    p = subs.add_parser("discover", help="Synthesize a certified polynomial invariant")
    p.add_argument("goal", type=Path)
    p.add_argument("--strategy", choices=("cegis", "random", "full_symbolic"), default="full_symbolic")
    p.add_argument("--budget", type=int, default=64)
    p.add_argument("--seconds", type=float, default=30)
    p.add_argument("--seed", type=int, default=20261007)
    p.add_argument("--archive", type=Path, default=ROOT / ".noetherforge/archive.sqlite")
    p.add_argument("--out", type=Path, required=True)
    p = subs.add_parser("check", help="Check a conjectured polynomial and return an exact counterexample")
    p.add_argument("goal", type=Path)
    p.add_argument("invariant")
    p = subs.add_parser("verify", help="Independently recheck a proof certificate")
    p.add_argument("certificate", type=Path)
    p = subs.add_parser("replay", help="Recheck all saved mathematical evidence in a run")
    p.add_argument("run", type=Path)
    p = subs.add_parser("benchmark", help="Compare baseline and evolved search with frozen task and budget controls")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--budget", type=int, default=64)
    p.add_argument("--seconds", type=float, default=30)
    p = subs.add_parser("evolve", help="Use a user-configured model proposer with verified feedback")
    p.add_argument("question")
    p.add_argument("--proposer-argv", type=Path, required=True, help="JSON array of executable and arguments; stdin/stdout JSON protocol")
    p.add_argument("--index", type=Path, default=ROOT / ".noetherforge/corpus.json")
    p.add_argument("--rounds", type=int, default=3)
    p.add_argument("--timeout", type=int, default=60)
    p.add_argument("--archive", type=Path, default=ROOT / ".noetherforge/archive.sqlite")
    p.add_argument("--out", type=Path, required=True)
    p = subs.add_parser("export-lean", help="Export a certified identity for separate Lean compilation")
    p.add_argument("certificate", type=Path)
    p.add_argument("out", type=Path)
    p = subs.add_parser('invent',help='Discover in polynomial dynamics, rational dynamics or inequality programs')
    p.add_argument('problem',type=Path)
    p.add_argument('--budget',type=int,default=200)
    p.add_argument('--seconds',type=float,default=90)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--ledger',type=Path,default=ROOT/'.noetherforge/claims.sqlite')
    p = subs.add_parser('ledger-check',help='Reverify every stored claim and its dependency evidence')
    p.add_argument('--ledger',type=Path,default=ROOT/'.noetherforge/claims.sqlite')
    args = parser.parse_args(argv)
    if args.command=='invent':
        from .laboratory import invent,save
        from .ledger import ClaimLedger
        ledger=ClaimLedger(args.ledger)
        try:
            result=invent(read(args.problem),args.budget,args.seconds,ledger)
            path=save(result,args.out)
            emit({'path':str(path),'status':result['status'],'metrics':result.get('metrics'),'claims':result.get('ledger_claims')})
        finally: ledger.close()
    elif args.command=='ledger-check':
        from .ledger import ClaimLedger
        ledger=ClaimLedger(args.ledger)
        try: emit(ledger.recheck())
        finally: ledger.close()
    elif args.command == "index":
        result = save_index(args.root, args.out)
        emit({"index": str(args.out), "counts": result["counts"], "upstream_commit": result["upstream_commit"], "source_sha256": result["source_sha256"]})
    elif args.command in {"search", "prepare"}:
        index = read(args.index)
        result = query(index, args.question, args.limit) if args.command == "search" else packet(index, args.question, args.limit)
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
            emit({"path": str(args.out)})
        else:
            emit(result)
    elif args.command == "discover":
        goal, archive = Goal.from_dict(read(args.goal)), Archive(args.archive)
        try:
            run = search(goal, args.strategy, args.budget, args.seed, args.seconds, archive)
            out = write_run(run, args.out)
            emit({"path": str(out), "status": run["status"], "metrics": run["metrics"], "invariants": [r["formula"] for r in run["accepted"]]})
        finally:
            archive.close()
    elif args.command == "check":
        goal = Goal.from_dict(read(args.goal))
        result = inspect_candidate(goal, parse(args.invariant, goal.variables))
        emit(result)
        return 0 if result["verification"]["status"] == "CERTIFIED_POLYNOMIAL_IDENTITY" else 2
    elif args.command == "verify":
        result = verify(read(args.certificate))
        emit(result)
        return 0 if result["status"].startswith("CERTIFIED_") else 2
    elif args.command == "replay":
        emit(replay(read(args.run)))
    elif args.command == "benchmark":
        result = run_benchmark(args.out, args.budget, seconds=args.seconds)
        emit({"path": str(args.out), "summary": result["summary"], "observed_gain_over_random": result["observed_gain_over_random"], "observed_gain_over_full_symbolic": result["observed_gain_over_full_symbolic"], "historically_novel_results_verified": 0})
    elif args.command == "evolve":
        archive = Archive(args.archive)
        try:
            result = evolve(read(args.index), args.question, read(args.proposer_argv), args.rounds, args.timeout, archive=archive)
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
            emit({"path": str(args.out), "round_statuses": [r["status"] for r in result["rounds"]]})
        finally:
            archive.close()
    elif args.command == "export-lean":
        emit(export_lean(read(args.certificate), args.out))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, KeyError, OSError) as error:
        print(f"Discovery error: {error}", file=sys.stderr)
        raise SystemExit(1)
