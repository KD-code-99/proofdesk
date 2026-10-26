# Changelog

## 0.2.0 — 16 October 2026

### Added

- Search a bounded coefficient template for a rational conservation law, with exact counterexamples and an independently checked result.
- Inspect exact finite recurrence orbits through a step slider, approximate plot and rational-value table.
- Save investigations across sessions, inspect past evidence and resume from any connected MCP client.
- Export all investigation evidence and audit it in the browser or with the offline command.
- Five investigation tools, evidence resources, output schemas, protocol/semantic regressions and CI.

### Fixed

- MCP mathematical calls now persist the evidence receipts they return.
- Concurrent stale investigation updates produce an actionable conflict instead of overwriting history.
- Refuted invariant results include exact before/after quantity values.
- Source hashes normalize CRLF/LF so receipts replay across Windows and Unix checkouts of the same source.

### Compatibility

- Existing three mathematical tools and run command remain available.
- Checker hashes changed. Replay an older receipt using its original source revision; version mismatches fail explicitly.
- Existing demo media and v0.1.1 release archives demonstrate the earlier version.
