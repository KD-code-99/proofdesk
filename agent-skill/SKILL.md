---
name: proofdesk-mathematics
description: Check supported rational invariants, compute exact modular recurrences, and inspect inequality certificates through ProofDesk's MCP tools.
---

# ProofDesk mathematical assistant

Use the configured ProofDesk MCP server. Translate the user's mathematical request into structured tool arguments, then call the relevant tool. Ask for missing variables, transitions or arithmetic domains before claiming a result.

- `check_invariant`: numerator and denominator polynomials; declared variables, recurrence transitions and fixed parameters. Report the exact nonzero domain guards. A fixed-parameter-only quantity is not a new state invariant.
- `recurrence_jump`: Fibonacci or affine recurrence, nonnegative step count and positive modulus. Report the modular result and the selected recurrence. The shortcut does not generalize to arbitrary programs.
- `check_inequality`: the displayed quadratic example and an exact proposed constant. A failed certificate is not a proof that the inequality is false.
- `discover_invariant`: synthesize a numerator of degree 1–3 for a specified denominator (default `x*y`) using counterexample-guided exact linear algebra. Report check count, bounds and verifier result. `NO_RESULT_WITHIN_TEMPLATE` is inconclusive, not a nonexistence proof. Do not claim a known formula is historically new.
- `trace_orbit`: inspect up to 24 exact recurrence steps from a small rational seed. A finite constant trace alone is not a proof. Report singularity and computation-limit stops.

For a multi-step question, call `start_investigation` with a title and supported problem. Use `advance_investigation` for `check`, `discover`, `trace` and `replay`, always including the current `expected_revision`. A revision conflict means another session advanced the work: get its current state before retrying. Successful discovery retains the certified quantity for orbit exploration. The user's original guess remains visible in the investigation history.

Use `list_investigations` and `get_investigation` to resume between sessions; never imply access to a different server's storage. Read `proofdesk://investigations/{id}` or `proofdesk://receipts/{id}` resources for structured evidence. `export_investigation` includes every referenced receipt. A user can audit that bundle using `python -B -m proofdesk.audit <file>`. Digests check content, not author identity. Replay requires the originating checker version.

Show the returned mathematical status, evidence type, explanation and receipt identity. For REFUTED, show the actual exact counterexample. For unsupported or invalid input, explain the limit. Never manufacture a proof, counterexample, elapsed time or novelty claim. Offer the receipt for independent replay.
