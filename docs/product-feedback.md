# Product feedback and observed friction

16 October 2026. These notes concern the tools actually used. No live Alexa+, Ring, Bee or AWS integration was tested in this update.

## MCP protocol and official TypeScript client

Used for initialization, discovery, typed mathematical results, persistent investigation actions and evidence resource reads. Structured content preserves certificates and exact counterexamples through the assistant boundary. The official client exposes a practical interoperability check. The local Python app remains free of third-party runtime dependencies; the optional interop harness installs the pinned official client.

Onboarding: the 2025-11-25 specification and Streamable HTTP documentation are the implementation reference. Our endpoint uses JSON responses and POST; GET correctly advertises 405/Allow. We would continue building with MCP because multiple clients can invoke the same bounded checker and resume the same evidence record.

Observed friction in **our implementation**:

| Task | Reproduction | Expected | Actual | Severity | Fix / actionable suggestion |
| --- | --- | --- | --- | --- | --- |
| Resume evidence created through MCP | Call `tools/call` in the baseline, then try to retrieve that receipt from local storage | The returned evidence receipt remains available | The baseline MCP path created a receipt without saving it; `/api/run` did save it | Important for our persistence feature | Route MCP results through storage too. Added resource-read and saved-receipt regressions. This is our server defect, not a protocol/SDK failure |
| Advance one investigation from two clients | Both clients read revision 0 and submit their next action | Neither silently overwrites the other's history | Concurrent writes require an explicit application-level conflict policy | Important design requirement | Add `expected_revision`; accept one write and return an actionable conflict to the other. A protocol example for revision-aware state tools would help implementers |
| Reproduce a result after a checker update | Replay a receipt made with different engine hashes | The version mismatch is visible | Replay intentionally rejects it | Important reproducibility constraint | Preserve source revisions; display the mismatch. A standardized evidence attachment carrying verifier/source identity would help |

The concurrency and versioning rows describe application design requirements tested here, not bugs in MCP or Amazon software. Do not submit them as confirmed upstream defects.

## Alexa+ track and simulator access

The [official FAQ](https://amazonappdev2026.devpost.com/details/faqs) clarifies that ordinary entrants cannot access the gated Alexa+ add-on SDK/toolkit/CLI/simulator and may use their own web client. We used the supported self-hosted MCP route and a local guided simulation. We did not attempt partner onboarding or test production device latency, voice quality, or customer authentication.

Feature requests, not claims of observed failures:

- **Important:** a downloadable evidence attachment that keeps exact result, domain and verifier version together.
- **Important:** presentation types distinguishing a certified statement, counterexample, finite trace and inconclusive bounded search.
- **Nice to have:** a public conformance example for persistent tools plus evidence resources and cross-session resumption.

We would build further assistant integrations if the production developer path becomes available. This answer reflects the open-protocol development experience; it does not imply production certification.
