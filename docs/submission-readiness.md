# Submission readiness: ProofDesk 0.2

Checked 16 October 2026 against the [official rules](https://amazonappdev2026.devpost.com/rules) and [FAQ](https://amazonappdev2026.devpost.com/details/faqs). Deadline: **23 October 2026, 22:00 Europe/Istanbul**.

## Entry path

Primary track: Alexa+. A real self-hosted MCP 2025-11-25 server over Streamable HTTP, demonstrated by the local simulated assistant. The browser initializes MCP, discovers tools and actually calls them. The gated Amazon simulator and a live Alexa+ connection are not required by the FAQ and are not claimed here.

Open Source mini challenge: the existing additional [proofdesk-mcp-client](https://github.com/KD-code-99/proofdesk-mcp-client) project is the proposed contribution. Check its link, license and compatibility with this update before final submission. Main-project source alone should not be described as an additional project. AWS Builder is not claimed because this build does not execute AWS services.

## Concrete readiness

| Item | Status / evidence |
| --- | --- |
| Source, assets, run instructions and license | In this repository; application MIT, vendored kernel Apache-2.0 |
| Working Alexa+ track technology | Real `/mcp`, ten tools, evidence resources; official SDK interop evidence |
| Significant new work | `NEW_WORK.md`, source changes and regression tests |
| Demonstrated audience | Students and developers investigating small rational recurrences; no unmeasured user-adoption claims |
| Product feedback | `docs/product-feedback.md`; observed implementation friction distinguished from requests |
| Public English video under 3 minutes | **Still required.** Existing media show 0.1.1; record 0.2 with the script below, upload publicly to YouTube/Vimeo, and add its URL to Devpost |
| Devpost form / entry confirmation | **Not submitted by this change.** Complete the form and retain its confirmation |
| Availability through judging | Keep source and runnable instructions accessible through 20 November; hosting is unnecessary for the FAQ's local path |

## A 165-second demonstration

Use an uncluttered local state directory: `python -B -m proofdesk --state-dir .state/demo/receipts`. Prepare the actual MCP client connection and a blank investigation. Record real interactions and keep waits visible. No copyrighted background music or third-party footage is needed.

| Time | Screen action | English narration |
| --- | --- | --- |
| 0–15s | Begin a Lyness investigation | “An assistant should be able to admit a mathematical guess is wrong—and help us find what is right. ProofDesk keeps the evidence for that whole investigation.” |
| 15–35s | Challenge `x+y`; show state and before/after | “This guess fails at an admissible exact state. These are rational values, not a language model's explanation standing in for a computation.” |
| 35–70s | Find a conserved quantity; open search history | “The search solves for coefficients in a declared template. Counterexamples reject bad candidates. Only the independent symbolic checker can certify the surviving identity, with its domain guards.” |
| 70–95s | Explore orbit; move step slider and show exact table | “Now we can explore the recurrence. The picture is approximate; the table is exact. A constant finite trace illustrates the identity; it is not itself the proof.” |
| 95–115s | Reload and resume saved investigation | “The next conversation can continue from this record. Any MCP client connected to this server can read the investigation and its receipts.” |
| 115–140s | Replay, export, audit the downloaded bundle | “The evidence travels with the claim. Replay reconstructs the mathematical result. An edited result fails audit even if someone recomputes a hash.” |
| 140–155s | Show quarter-turn search or actual second MCP client's resource read | “This is a computation on supplied transitions, not a hard-coded replacement formula. The same workflow handles another supported recurrence.” |
| 155–165s | Scope and closing frame | “Built for the Alexa+ track using actual MCP and a clearly labeled local simulation. The new work is the persistent investigation experience. The bounded checker states what it can and cannot establish.” |

## Final form checks

- Insert the new public video URL; do not substitute a GitHub MP4 link.
- Use the final branch/commit or release containing 0.2; old v0.1.1 archive lacks the investigation tools.
- Paste the new-work explanation, product feedback for technologies actually used, primary track, and the additional Open Source contribution details.
- Only submit friction that was actually observed. Do not present this server's own bugs as Amazon service defects.
- Verify a clean download can run the exact demonstrated version, then retain Devpost's submitted-project URL/status.
