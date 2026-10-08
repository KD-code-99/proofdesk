# ProofDesk: mathematical answers that leave evidence

Submission text draft. The public video URL is supplied separately; this document is not a Devpost submission receipt.

Primary track: Alexa+. Platform path: MCP server with a working simulated Alexa+ web interface. Public repository: https://github.com/KD-code-99/proofdesk. Video: media/demo-narrated.mp4; public YouTube/Vimeo upload pending.

## Inspiration

An assistant can describe a formula convincingly even when the formula is wrong. ProofDesk turns a mathematical guess into a checkable result: an exact counterexample when the guess fails, or a supported certificate with explicit domain guards when it succeeds. I built it for people studying small dynamical systems who need to inspect the evidence behind an assistant's answer. My existing exact mathematical kernel made that distinction a practical product feature.

## What it does

ProofDesk checks a proposed conservation law and produces either a certificate with its domain or a concrete counterexample. It also jumps to far-future states of supported recurrences using exact modular arithmetic and explains a supported sharp inequality using a sum-of-squares certificate and equality witness. Every result can be downloaded and recomputed.

## How we built it

I wrapped the existing Apache-2.0 NOETHER-FORGE kernel in new, bounded MCP tools. The new server implements protocol 2025-11-25 using Streamable HTTP and JSON responses. The interface demonstrates the Alexa+ use case locally, and the Agent Skill explains how an assistant should invoke the tools and report their limited verdicts. Receipt replay recomputes the mathematical check with pinned engine hashes. The Python application has no third-party runtime dependencies.

## Demonstration

Start with the Lyness map `(x,y,a) → (y,(a+y)/x,a)` and ask whether `x+y` is conserved. The checker finds an exact admissible state where it changes. Replace it with `(x+1)*(y+1)*(x+y+a)/(x*y)` and check the uniform rational identity and its guards. Replay that result. Then compute Fibonacci modulo `1000000007` at `10^30` steps and inspect the supported sharp bound with constant 2.

## What changed during the hackathon

The kernel existed before this event. The MCP server, tool schemas, receipts, replay API, assistant interface, skill, tests and demo were built during the event window. The known formulas are demonstration controls, not claims of newly discovered mathematics.

## Product feedback

MCP gives the mathematical service a clear separation between assistant intent and exact tool results. The JSON tool schema makes a supported domain visible, and structured results preserve certificates instead of reducing them to prose. Local onboarding is inexpensive because the application has no runtime dependencies. A useful Alexa+ platform feature would be a dedicated result presentation for certified statements, counterexamples and explicit unknowns, plus a downloadable evidence attachment. This is a proposed feature, not a claim that Alexa+ was tested in production.

I would build further mathematical assistant integrations with this interface. During local SDK interoperability testing, an unknown-tool request exposed an error-handling mismatch in my server; I corrected it and retained a regression test. This is observed development feedback from my own MCP implementation, rather than an Alexa+ production issue. AWS services were not used, so the AWS Builder mini challenge is not claimed. The separate published MCP client below is the additional Open Source contribution.

## Testing and AI usage

Twelve acceptance tests pass. They compare shortcuts with direct recurrence computation, check exact counterexamples, reject altered receipts and exercise the MCP transport. The official MCP client 2.3.1 initializes the server, discovers all three tools and executes the refutation, invariant, recurrence and inequality cases in both default and automatic negotiation modes. The extracted test build also passed its central workflow. This is executed local interoperability evidence, rather than official certification or a live Alexa+ connection.

Review the [actual test output](https://github.com/KD-code-99/proofdesk/blob/codex/amazon-proofdesk/evidence/tests.txt), [official SDK interoperability results](https://github.com/KD-code-99/proofdesk/blob/codex/amazon-proofdesk/evidence/official-sdk-interop.json), and [complete v0.1.1 test build](https://github.com/KD-code-99/proofdesk/releases/download/v0.1.1/proofdesk-test-build.zip). Extract the build and run `python -B -m proofdesk` with Python 3.12 or newer; open `http://127.0.0.1:4186`. To run acceptance tests, use `python -B -m unittest discover -s tests -v`.

I am the solo entrant. Codex assisted with implementation, tests and documentation. Correctness claims depend on the executed exact computations and independent checks.

## Limitations and next steps

This is bounded mathematical software, not a general theorem prover. The web interface is an explicitly simulated Alexa+ experience. A public deployment needs authentication; the local demo does not claim a live Alexa connection. The next product step is an authenticated deployment that preserves structured verdicts, domain guards and downloadable evidence through the assistant interaction.

## Additional Open Source mini challenge contribution

Separate project: https://github.com/KD-code-99/proofdesk-mcp-client. GitHub username: KD-code-99. A dependency-free MCP client performs actual protocol initialization, catalog discovery and mathematical tool calls, preserving the structured certificate/counterexample and downloadable receipt. Its acceptance evidence covers an actual local server, a conserved quantity, a refuted guess and a `10^30`-step recurrence. It was created during the event as an additional licensed project alongside the main entry.

Verified contribution commit: https://github.com/KD-code-99/proofdesk-mcp-client/commit/c7c750911d3f529e2d6272e442c716c19c43dc28
