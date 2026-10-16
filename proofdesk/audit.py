"""Offline replay: python -B -m proofdesk.audit investigation.json."""
import argparse
import json
from pathlib import Path
import sys

from .investigations import audit_bundle


def main():
    parser = argparse.ArgumentParser(description="Independently replay every mathematical receipt in a ProofDesk investigation.")
    parser.add_argument("bundle", type=Path)
    args = parser.parse_args()
    try:
        if args.bundle.stat().st_size > 4 * 1024 * 1024:
            raise ValueError("Bundle exceeds the 4 MiB audit limit")
        result = audit_bundle(json.loads(args.bundle.read_text(encoding="utf-8")))
    except (OSError, ValueError, KeyError, TypeError, SyntaxError, ZeroDivisionError) as error:
        print(json.dumps({"status": "AUDIT_FAILED", "error": str(error)[:250]}))
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
