# ProofDesk: mathematical answers that leave evidence

Status: draft. Registration, rules attestation, public video upload and final Devpost submission remain external steps. The local build and test results do not imply any of those steps occurred.

Primary track: Alexa+. Platform path: MCP server with a working simulated Alexa+ web interface. Public repository: https://github.com/KD-code-99/proofdesk (verify after publication). Video: media/demo-narrated.mp4; public YouTube/Vimeo upload pending.

## Inspiration

An assistant can describe a formula convincingly even when the formula is wrong. People using assistants to study dynamical systems or inspect a numerical claim need a way to distinguish a plausible answer from a checked one. Our existing exact mathematical kernel made that distinction a practical product feature.

## What it does

ProofDesk checks a proposed conservation law and produces either a certificate with its domain or a concrete counterexample. It also jumps to far-future states of supported recurrences using exact modular arithmetic and explains a supported sharp inequality using a sum-of-squares certificate and equality witness. Every result can be downloaded and recomputed.

## How we built it

We wrapped the existing Apache-2.0 NOETHER-FORGE kernel in new, bounded MCP tools. The new server implements protocol 2025-11-25 using Streamable HTTP and JSON responses. The interface demonstrates the Alexa+ use case locally, and the Agent Skill explains how an assistant should invoke the tools and report their limited verdicts. Receipt replay recomputes the mathematical check with pinned engine hashes.

## Demonstration

Start with the Lyness map `(x,y,a) → (y,(a+y)/x,a)` and ask whether `x+y` is conserved. The checker finds an exact admissible state where it changes. Replace it with `(x+1)*(y+1)*(x+y+a)/(x*y)` and check the uniform rational identity and its guards. Replay that result. Then compute Fibonacci modulo `1000000007` at `10^30` steps and inspect the supported sharp bound with constant 2.

## What changed during the hackathon

The kernel existed before this event. The MCP server, tool schemas, receipts, replay API, assistant interface, skill, tests and demo were built during the event window. The known formulas are demonstration controls, not claims of newly discovered mathematics.

## Product feedback

MCP gives the mathematical service a clear separation between assistant intent and exact tool results. The JSON tool schema makes a supported domain visible, and structured results preserve certificates instead of reducing them to prose. Local onboarding is inexpensive because the application has no runtime dependencies. A useful Alexa+ platform feature would be a dedicated result presentation for certified statements, counterexamples and explicit unknowns, plus a downloadable evidence attachment. This is a proposed feature, not a claim that Alexa+ was tested in production.

We would build further mathematical assistant integrations with this interface. AWS services were not used, so the AWS Builder mini challenge is not claimed. An Open Source mini challenge answer should only be added after the separate contribution URL is published and verified.

## Testing and AI usage

See README.md for a source/test-build launch and unittest command, and evidence/tests.txt for actual output. Tests compare shortcuts with direct recurrence computation, check exact counterexamples, reject altered receipts and exercise the MCP transport. Codex assisted with implementation, tests and documentation. Correctness claims depend on executable checks.

## Limitations and next steps

This is bounded mathematical software, not a general theorem prover. The web interface is an explicitly simulated Alexa+ experience. A public deployment needs authentication; the local demo does not claim a live Alexa connection. Public video hosting and personal registration answers are still required before final submission.

## Additional Open Source mini challenge contribution

Separate project: https://github.com/KD-code-99/proofdesk-mcp-client (verify publication). GitHub username: KD-code-99. A dependency-free MCP client performs actual protocol initialization, catalog discovery and mathematical tool calls, preserving the structured certificate/counterexample and downloadable receipt. Its acceptance evidence covers an actual local server, a conserved quantity, a refuted guess and a `10^30`-step recurrence. It was created during the event as an additional licensed project alongside the main entry.
