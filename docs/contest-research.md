# ProofDesk contest research and evolution brief

Research checked on 16 October 2026. Repository baseline: `6cedef20fcd44129d222445fe4976c1a65810cfa`. This note separates official requirements, observations of that baseline, and proposed work. It is not a prediction of judging results or evidence of market novelty.

## Decision

Evolve ProofDesk from three mathematical demonstrations into a persistent investigation assistant: **bring a conjecture, see exactly why it fails, repair it within a declared search space, and carry the evidence into the next conversation**. A wrong guess should be the opening of a useful investigation, rather than a dead end or a red badge.

The existing exact checker is the product's strongest asset. Additional integrations should serve this investigation loop. A large catalog of unrelated tools would make the product harder to explain and its correctness harder to assess.

## Contest facts that affect the build

The overview names technical implementation, design, potential impact and quality of the idea. It requests a project description, GitHub source and run instructions, a public English YouTube/Vimeo demo shorter than three minutes, product feedback, track selection, and an account of changes to pre-existing work. The Open Source mini challenge requires an additional project or public contribution, with a contribution URL, repository URL, username and explanation. AWS Builder requires documented use of an eligible AWS service or development tool. These are submission requirements, not evidence of a likely prize. [Official overview](https://amazonappdev2026.devpost.com/)

The submission window is 31 August–23 October 2026, ending at 12:00 Pacific Time: **22:00 Istanbul on 23 October**. Judging runs 9–20 November. Existing software must be significantly updated during the window. Alexa+ accepts a self-hosted MCP 2025-11-25+ server over Streamable HTTP, an Agent Skill, or the permitted simulated-experience path. All four judging criteria have equal weight. The rules explicitly contrast basic wrappers with persistent, agentic and media-rich experiences. Honest friction logs can earn a bonus of up to 10%; useful entries specify task, steps, expectation, actual result, severity, workaround and suggestion. Judges may rely on submission media, so the video must demonstrate the distinguishing behavior. Preserve access to the runnable project through judging. [Official rules](https://amazonappdev2026.devpost.com/rules)

Gated Alexa+ SDKs, toolkit, CLI and Amazon simulator are unavailable to ordinary entrants. The FAQ permits a local repository plus video and expressly accepts a web page that performs real MCP initialization, discovery and tool calls. Hardware and continuous hosting are unnecessary for this track. Do not describe a local simulation as a production Alexa+ integration. [Official FAQ](https://amazonappdev2026.devpost.com/details/faqs)

The resources page points Alexa+ entrants to Agent Skills and Streamable HTTP. It records that promotional credit codes ran out on 7 October; do not plan the build around obtaining a new code. [Official resources](https://amazonappdev2026.devpost.com/resources)

## Baseline gap evaluation

These are qualitative engineering observations, not assigned contest scores. Source links refer to the reviewed checkout.

| Dimension | What the baseline already demonstrates | Gap worth closing | Evidence to retain |
| --- | --- | --- | --- |
| Technical implementation | Exact rational checks, modular recurrence shortcuts, certificate checking, receipts and JSON MCP | The browser executes one tool at a time; investigations and MCP-accessible persistent context are absent | Actual protocol calls, negative cases, restart persistence, independently replayed output |
| Design | Clear verdicts, explicit limits, downloadable receipt | An unsuccessful conjecture ends the flow; raw JSON carries most explanatory detail | A person can move from failure to an explained repair without editing JSON |
| Potential impact | Specific use for people exploring small dynamical systems | No demonstrated multi-session study or teaching workflow | Reopen a saved investigation, explain the counterexample and continue with the same assumptions |
| Quality of idea | Evidence rather than unsupported mathematical prose | Three disconnected calculators do not yet tell a distinct product story | A visible lineage from original guess through witness to certified replacement |

Baseline evidence: [README](../README.md), [mathematical tools](../proofdesk/math_tools.py), [transport](../proofdesk/server.py), [receipt replay](../proofdesk/receipts.py), [browser client](../web/app.js), [submission draft](../devpost-submission.md).

Concrete baseline details:

- The interface already initializes MCP and calls tools over `/mcp`. Add catalog discovery to the visible diagnostic path so the demonstration documents the complete client interaction.
- MCP mathematical calls create receipts but the baseline server does not persist those receipts through `Store.save`; the separate `/api/run` path does. A persistent investigation must save the evidence created through its actual MCP path.
- Browser state consists chiefly of `mode` and `lastReceipt`. Refreshing does not restore an investigation, a branch, or an explanation.
- The inequality control checks a supplied certificate. An invalid certificate alone must never be presented as a false inequality.
- Replay checks current engine hashes. Changing checker code can invalidate earlier release receipts; release provenance and migration behavior must be explicit.

## Recommended product increments

### 1. Counterexample-guided repair investigation

Create one investigation containing the original statement, declared recurrence/domain, checker verdict, exact witness, attempted repairs and receipt identities. Present a sequence such as: “I guessed `x+y` stays constant” → “Here is an admissible state where it changes” → “Find a quantity that does survive” → “This replacement is checked under these guards.”

The repair source must be honest. A known formula selected from a small library is a suggested known repair. A bounded enumeration is a bounded search. Neither is a mathematical discovery or proof of completeness. Feed every proposed repair back through the checking kernel before displaying a certified result. Preserve unsuccessful attempts because they explain why the assistant changed its answer.

Acceptance: demonstrate at least one repaired conjecture, one rejected repair, one unsupported request, and one parameter-only trivial result. A failed search returns an explicit unresolved status.

### 2. Evidence people can interrogate

Render the counterexample as exact before/after arithmetic, not just a coordinate dictionary. Let the user inspect a short orbit, change an admissible starting state, and compare the rejected quantity with the certified one. Plots are explanatory views of selected states; the symbolic certificate establishes the universal identity. Label this distinction beside the visual.

Show domain exclusions as part of the result. A zero denominator should produce a helpful explanation, not a misleading data point. Keep large modular integers as strings through JSON and JavaScript to avoid precision loss.

Acceptance: visual values agree with exact tool evidence; the user can inspect the underlying fractions; excluded states cannot acquire a success badge.

### 3. An investigation that survives the session

Persist titles, statements, attempts and evidence locally. Restore an investigation after a server restart. Export an evidence bundle that includes its lineage and replayable receipts. Where possible, each transition should identify the receipt and assumptions it used, so “continue that investigation” has a concrete referent.

Use stable IDs and validated resource URIs. Keep computational output separate from generated explanations. Storage success is not proof success, and a receipt digest is not a signature.

Acceptance: restart, reopen, add an attempt, export, and replay the supported mathematical results. Reject altered receipt content and unknown investigation IDs.

### 4. A small conversational surface

Support clear intents such as “investigate this invariant,” “show why it failed,” “try a repair,” “continue my last investigation,” and “export the evidence.” A deterministic local intent router is acceptable if labelled. If adding a model, make it propose tool inputs and explanations while the exact checker owns mathematical verdicts. Do not silently convert free-form requests into a convenient canned example.

Voice input can be a useful optional control, but typed input and keyboard access must remain usable. Browser speech support must be detected; do not claim actual Echo support from a microphone demo.

## MCP features with practical value

### Implement first: resources and structured result schemas

MCP resources support discovery, reads and parameterized URI templates; support must be declared during initialization. Proposal: `proofdesk://investigations/{id}` and `proofdesk://receipts/{id}` expose portable context to any suitable client. Start without subscriptions; only advertise notifications if implemented. [MCP 2025-11-25 resources](https://modelcontextprotocol.io/specification/2025-11-25/server/resources)

Tools can declare `outputSchema`. If declared, the server must return matching `structuredContent`; clients should validate it. Continue supplying a text serialization for compatibility. Use resource links to point from a result to saved evidence. State-writing investigation tools need appropriate annotations rather than inheriting read-only hints from mathematical checks. [MCP 2025-11-25 tools](https://modelcontextprotocol.io/specification/2025-11-25/server/tools)

For Streamable HTTP, each message is a POST; JSON responses are allowed and SSE is optional. A server without GET streaming may return 405. Keep localhost binding and Origin validation. Send the negotiated protocol header and correct Accept headers from clients. [MCP 2025-11-25 transport](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports)

### Optional: an actual MCP App evidence view

MCP Apps is a separate extension. Tools refer to a `ui://` HTML resource through `_meta.ui.resourceUri`; a supporting host fetches it and establishes sandboxed bidirectional communication. Host support varies. An ordinary standalone web UI is not automatically an MCP App. If implemented, test the host bridge and provide the regular browser interface as a fallback. [Official MCP Apps overview](https://modelcontextprotocol.io/extensions/apps/overview)

An interactive evidence panel is a good future extension: tool output updates the panel, the user inspects witnesses, and the panel requests another check without losing context. Its value is the preserved investigation, not the presence of an iframe.

### Defer until a real need exists

MCP tasks were introduced in 2025-11-25 and remain experimental; they require capabilities and lifecycle handling. They suit genuinely long searches. A synchronous bounded repair should stay synchronous. [MCP tasks](https://modelcontextprotocol.io/specification/2025-11-25/basic/utilities/tasks)

Elicitation lets a server request missing information through a supporting client. Only use supported modes after capability negotiation; form requests are for non-secret inputs. A local ordinary form already solves the present mathematical-input problem. [MCP elicitation](https://modelcontextprotocol.io/specification/2025-11-25/client/elicitation)

## Submission work that still needs evidence

The baseline draft says a public video upload is pending. Recording a new video is necessary after the product changes: old footage does not demonstrate the new flow. A practical 165-second storyboard is: 15 seconds for the customer problem; 40 for the wrong guess and exact witness; 40 for checked repair and interactive evidence; 35 for reopening and replay; 20 for actual MCP calls and limits; 15 for the concise result.

Update `NEW_WORK.md` with the actual new components, dates and tested revision. Preserve the existing kernel provenance and licenses. Replace old test-count claims with fresh outputs. Identify the additional Open Source contribution separately; improving only the primary repository should not be described as the already-completed additional project.

Feedback should discuss tools actually used. Capture reproducible friction when encountered and identify whether it belongs to this server, a client, a standard, documentation, or an unavailable Amazon preview. Do not invent platform defects to obtain a bonus. Record environment, steps, result and workaround while testing, then submit only supported entries.

The existing separate MCP-client URL in the draft should be reverified before claiming the mini challenge. AWS integration remains optional: do not claim AWS Builder unless a documented eligible tool/service was actually used. All remaining external submission steps should be reported as pending until their resulting URLs or receipts have been checked.

## Guardrails for bold claims

The defensible differentiation is an inspectable, persistent repair workflow over a bounded exact mathematical engine. This research did not establish first-in-market status, user demand, learning gains, generalized theorem-proving ability, actual Alexa+ production access, or a likely prize. These would require separate evidence. The product can be ambitious while being exact about what it knows.
