"""Public entry point for the complete release audit."""
import argparse
from .release_audit import audit

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--out',type=__import__('pathlib').Path,required=True)
    raise SystemExit(audit(parser.parse_args().out))
