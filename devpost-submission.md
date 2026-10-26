# ProofDesk: mathematical answers that leave evidence

Submission text draft. The public video URL is supplied separately; this document is not a Devpost submission receipt.

Primary track: Alexa+. Platform path: MCP server with a working simulated Alexa+ web interface. Public repository: https://github.com/KD-code-99/proofdesk. Video: media/demo-narrated.mp4; public YouTube/Vimeo upload pending.

**0.2 update, 16 October:** the linked existing MP4 shows the earlier build. Record and upload the new investigation flow using [the submission script](docs/submission-readiness.md) before entering. This file is updated project copy, not a submitted entry.

## Inspiration

An assistant can describe a formula convincingly even when the formula is wrong. ProofDesk turns a mathematical guess into a checkable result: an exact counterexample when the guess fails, or a supported certificate with explicit domain guards when it succeeds. I built it for people studying small dynamical systems who need to inspect the evidence behind an assistant's answer. My existing exact mathematical kernel made that distinction a practical product feature.

## What it does

ProofDesk turns a wrong mathematical guess into a persistent investigation. It checks the guess, shows exact before/after values at a counterexample, searches a declared coefficient template for a replacement conservation law, and independently checks every proposed repair. An interactive orbit view lets a person inspect exact recurrence states. Saved history can be resumed by another MCP client, and a portable investigation bundle contains every receipt for offline replay. The original recurrence-jump and sharp-inequality workflows remain available.

## How we built it

I wrapped the existing Apache-2.0 NOETHER-FORGE kernel in bounded MCP tools. The server implements protocol 2025-11-25 over Streamable HTTP with JSON responses, ten tools, output schemas and evidence resources. A deterministic counterexample-guided search uses exact linear algebra to propose coefficients; a separate symbolic verifier certifies candidates. Persistent investigations use revision checks and atomic record replacement. The interface is a clearly labeled local Alexa+ simulation with four routed text intents, not a general language model or production Alexa connection. The Agent Skill explains how an assistant can use the same stateful tools. Receipt replay reconstructs the mathematical result with engine hashes. The Python app has no third-party runtime dependencies.

## Demonstration

Start with the Lyness map `(x,y,a) → (y,(a+y)/x,a)` and ask whether `x+y` is conserved. The checker finds an exact admissible state where it changes. Ask the search to find a conserved quantity with denominator `x*y` and numerator degree at most 3. Inspect the rejected candidates and their counterexamples, then the certified result and domain. Explore its orbit, reload and resume, and export/replay the full investigation. Show the quarter-turn recurrence to demonstrate another computed result. The known conservation laws are controls, not claims of new mathematics.

## What changed during the hackathon

The kernel existed before this event. The initial MCP server, tool schemas, receipts, replay API, assistant interface, skill, tests and demo were built during the event window. On 16 October I added coefficient synthesis, exact orbits, persistent cross-session investigations, evidence resources, bundle audit and a connected interface. `NEW_WORK.md` names the starting revision and distinguishes new adapters from pre-existing mathematical algorithms.

## Product feedback

MCP gives the mathematical service a clear separation between assistant intent and exact tool results. The JSON tool schema makes a supported domain visible, and structured results preserve certificates instead of reducing them to prose. Local onboarding is inexpensive because the application has no runtime dependencies. A useful Alexa+ platform feature would be a dedicated result presentation for certified statements, counterexamples and explicit unknowns, plus a downloadable evidence attachment. This is a proposed feature, not a claim that Alexa+ was tested in production.

I would build further mathematical assistant integrations with this interface. During local SDK interoperability testing, an unknown-tool request exposed an error-handling mismatch in my server; I corrected it and retained a regression test. This is observed development feedback from my own MCP implementation, rather than an Alexa+ production issue. AWS services were not used, so the AWS Builder mini challenge is not claimed. The separate published MCP client below is the additional Open Source contribution.

## Testing and AI usage

Acceptance tests compare shortcuts and orbit values with independent direct computations, check discovery on two recurrence families, preserve inconclusive search limits, reject forged evidence, verify restart persistence and concurrent-write conflicts, and exercise MCP resources and transport. The pinned official MCP client 2.3.1 discovers all ten tools and executes the full investigation through check, discovery, trace, replay, resource resumption and export in both legacy and automatic negotiation modes. Current executed evidence is retained under `evidence/`. This is local interoperability evidence, not official certification or a live Alexa+ connection.

Review the [actual test output](https://github.com/KD-code-99/proofdesk/blob/codex/amazon-proofdesk/evidence/tests.txt), [official SDK interoperability results](https://github.com/KD-code-99/proofdesk/blob/codex/amazon-proofdesk/evidence/official-sdk-interop.json), and [complete v0.1.1 test build](https://github.com/KD-code-99/proofdesk/releases/download/v0.1.1/proofdesk-test-build.zip). Extract the build and run `python -B -m proofdesk` with Python 3.12 or newer; open `http://127.0.0.1:4186`. To run acceptance tests, use `python -B -m unittest discover -s tests -v`.

I am the solo entrant. Codex assisted with implementation, tests and documentation. Correctness claims depend on the executed exact computations and independent checks.

## Limitations and next steps

This is bounded mathematical software. Search uses a chosen denominator, a numerator degree of 1–3, and at most 32 certificate checks; failure within that template is inconclusive. Finite traces illustrate behavior rather than prove a uniform identity. Digests do not establish authorship. An authenticated deployment and a production assistant integration remain future work. Product feedback and observed local development friction are detailed in [docs/product-feedback.md](docs/product-feedback.md); no untested Amazon service behavior is claimed.

## Additional Open Source mini challenge contribution

Separate project: https://github.com/KD-code-99/proofdesk-mcp-client. GitHub username: KD-code-99. A dependency-free MCP client performs actual protocol initialization, catalog discovery and mathematical tool calls, preserving the structured certificate/counterexample and downloadable receipt. Its acceptance evidence covers an actual local server, a conserved quantity, a refuted guess and a `10^30`-step recurrence. It was created during the event as an additional licensed project alongside the main entry.

Verified contribution commit: https://github.com/KD-code-99/proofdesk-mcp-client/commit/c7c750911d3f529e2d6272e442c716c19c43dc28
