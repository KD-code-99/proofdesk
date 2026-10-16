# Design verification

This pass extends ProofDesk's incumbent mathematical workbench. It preserves the paper-and-forest palette, Georgia headings, system body text, monospaced mathematical evidence, navigation buttons, forms, and replayable receipt pattern. It does not introduce a new visual system. No PRODUCT.md or DESIGN.md existed for this extension; no new DESIGN.md or token sidecar is needed under the Impeccable documenter's ordinary-extension rule.

## Preserved system

- Palette: paper `#f7f5f0`, surface `#fffefa`, ink `#202824`, forest `#275941`, line `#d9ded6`, and soft green `#e6ede5`. Amber and red remain reserved for uncertain and refuted results.
- Typography: Georgia/serif headings; `15px/1.6` system body text; monospaced expressions, inputs, receipts, and tabular exact values. The investigation heading uses `36px`, reducing to `30px` below the existing `768px` mobile breakpoint.
- Shape and spacing: existing `8px` container radius, `4px` control radius, fine borders, and the recurring `8px` spacing unit. The extension uses the same primary forest button and outlined secondary controls.
- Layout: existing desktop sidebar and workspace; stacked mobile layout with wrapping workflow navigation and investigation actions. Long expressions and receipt identifiers wrap; the exact-values table has its own scroll region.
- Evidence: the shared result surface still places the result, mathematical detail, receipt, replay/download controls, certificate disclosure, and scope statement together.

## Changes relevant to this extension

`web/style.css` strengthens muted text from `#68716a` to `#566158`. Functional receipt buttons, status pills, empty-state labels, form-footer notes, scope statements, and connection code have an `11px` minimum override. Existing eyebrow text is increased from `10px` to `11px`; its letter spacing is reduced to `.08em`. Workflow buttons have a `56px` minimum height. Mathematical result detail loses its decorative left border and preserves line breaks.

History rows in `web/investigations.js` now state their action explicitly: “View counterexample”, “View conserved quantity”, or “View exact orbit”, with suitable fallback labels. Their buttons have persistent underlines in `web/style.css`. This resolves the reviewed ambiguity in recognizing an evidence row as an actionable control while retaining the incumbent list-and-rule treatment.

The investigation surface follows a single visible sequence: start or resume a recurrence, challenge its conjecture, search for a conserved quantity, inspect its exact orbit, then replay or export the evidence. Existing result and receipt patterns carry the new outputs. The local assistant input states its four routed intents; adjacent copy explicitly calls it a guided simulation with no production Alexa connection. Search controls expose the denominator and maximum numerator degree; orbit controls expose the seed and step count. Result scope distinguishes finite samples from a symbolic proof, and the plot caption identifies visual approximation beside exact rational values.

## Evidence and limits

Source inspected: `web/index.html`, `web/style.css`, `web/app.js`, and `web/investigations.js`. The inherited focus-visible treatment uses a `3px` forest outline with a `3px` offset. History controls are native buttons, the orbit slider has a label, the exact-values scroll region is focusable and named, table headers have column scope, and activity uses a polite live status region. These are source checks, not a separate keyboard or screen-reader test by this documentation pass.

The final supplied captures were inspected directly:

- `../.impeccable/review/desktop.png` — `1425 × 2465` full-page image: desktop navigation, resumed investigation at revision 3, three explicitly actionable history rows, simulation disclosure, orbit result, exact table, and receipt controls.
- `../.impeccable/review/mobile.png` — `375 × 3138` full-page image: stacked navigation and forms, wrapped controls and formula, the same history and orbit result, receipt wrapping, and the final scope statement.

These captures show the resumed Lyness investigation and exact-orbit result. They do not establish every workflow, expanded search/certificate disclosure, loading/error state, export dialog, keyboard interaction, or intermediate viewport. The finish review supplied for this pass marked the history-affordance fix resolved and gave that fix a ship disposition; this record does not broaden that disposition to unobserved states or independently rerun the browser checks.

Inherited compact metadata, eyebrow labels, and glyph marks remain visible in the build. They are recorded as incumbent drift rather than new rules for future interfaces; this ordinary extension did not authorize a wholesale typography or identity redesign. The existing small-text rules are not canonized as a new design system.
