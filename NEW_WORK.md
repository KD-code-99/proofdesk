# Work created during the submission window

Date: 8 October 2026. Event: Build, Ship, Shape: Amazon Developer Hackathon. Primary track: Alexa+.

Pre-existing: the Apache-2.0 NOETHER-FORGE kernel and two known mathematical example certificates. Original checkout commit and copied-file hashes are retained in vendor/PROVENANCE.json.

New: bounded mathematical tool schemas; MCP 2025-11-25 transport; stateless tool dispatch; content-addressed receipts with engine identity; exact input/result replay; a simulated Alexa+ mathematical workbench; counterexample, long-recurrence and sharp-bound interactions; an Agent Skill; meaningful controls and HTTP acceptance tests; demo assets and source/test-build packaging.

No existing manuscript or mathematical formula is presented as a new discovery. There is no claim of live Alexa service access or AWS runtime use. The principal demonstration is the working mathematical MCP server and its local interface.

## 16 October 2026: investigation experience (0.2)

Starting revision: `6cedef20fcd44129d222445fe4976c1a65810cfa`.

- Added a deterministic, bounded counterexample-guided synthesis adapter. It computes rational invariant candidates from recurrence transitions, a chosen denominator and a numerator degree cap; the existing separate kernel checks every candidate. The vendored mathematical source is unchanged. This adapter builds on the kernel's pre-existing exact polynomial arithmetic and linear solver; neither the mathematics nor the discovery technique is claimed as novel research.
- Added exact finite orbit exploration, with rational values, a bit limit and explicit domain stops. Added exact before/after values to refuted-conjecture output.
- Added persistent investigations with optimistic revisions, atomic record replacement, events, resume, portable export and offline bundle audit. Audits check event/verdict correspondence and recompute evidence.
- Added five state tools and MCP resources, declared output schemas, browser catalog discovery, and persisted MCP receipts. The catalog now contains ten tools.
- Added a guided local intent interface, search controls, history inspection, an interactive orbit plot and exact table. Existing three mathematical workflows remain available.
- Added regression tests, official-client workflow/resource/export checks, reproducible dependency locking for that optional check, and CI. Updated research, feedback, demo script and submission materials.

Scope remains explicit: no production Alexa connection, AWS service usage, generalized theorem proving, market-first claim, or new mathematical discovery is asserted. The older video and v0.1.1 archive do not demonstrate this update.
