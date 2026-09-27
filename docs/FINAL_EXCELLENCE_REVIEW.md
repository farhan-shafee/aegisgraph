# Final excellence review

Decision memo recorded on 2026-09-27, before implementation, against
`23edc8473242d46b740119c17d4357288e91bd69`. This is a bounded refinement of V2.

## Decision memo

**A. Already excellent.** Deterministic detection and correlation, independently
validated typed analyst claims, separate human review, bounded replay, full-corpus
rule regression, and honest unsigned-bundle verification already support the
project's thesis. Public reads and deterministic analysis have strong denial and
database-preservation tests. Architecture, threat model, ADRs, code guide, and
historical versus current validation records are discoverable and candid.

**B. Senior-engineer weakness.** Replay reports scenario-wide rule totals but not
the exact principal/window decision. Approved administration actually produces
two rules, one family, and a nine-minute alert span: both diversity minimums fail.
The live UI requires the reviewer to derive this. Equal-time alert ordering also
depends on input order; reversing identical Atlas signals changes the derived
incident ID despite identical evidence. Current callers are stable, so this is a
latent invariant weakness rather than an observed production failure.

**C. Five-minute weakness.** The overview already says “Every conclusion must
survive inspection” and links replay, but the visitor must choose the strongest
positive, negative, and regression examples manually.

**D. Existing but less discoverable.** Scenario deep links already work.
APP-002 has three fixed comparisons but cannot initially select one through its
URL. Source drawers, linked detections, entities, hypothesis citations, and review
documentation already supply the provenance chain; a new trace page is redundant.

**E. Reinforce inspection.** Explain the actual reached correlation decision using
the same cluster partition and qualification predicates as incident creation.
Expose the existing strongest examples with a small set of stable links.

**F. Merely enlarge the repository.** A comparison dashboard, new trace subsystem,
recorded-review pipeline, signing infrastructure, extra detectors, and broad fuzz
tooling are unnecessary. Existing local workflow tests demonstrate human approval;
the public screenshot shows an open review, not a completed human decision.

| Rank | Candidate | Decision |
| --- | --- | --- |
| P0 | Positive/negative correlation receipts | Implement inside the existing replay panel; derive principal, anchored window, exact counts, minimums, outcome, and unmet conditions. |
| P1 | Equal-time signal ordering | Add a deterministic tie-break and permutation coverage, preserving canonical Atlas and corpus outcomes. |
| P1 | Three-step discovery and APP-002 deep link | Reuse the overview callout and validate the comparison against the fixed catalog. |
| P2 | Separate suspicious/benign comparison | Existing replay plus receipts and direct links suffice. |
| P2 | Recorded local-review artifact | Existing executable workflow tests and documentation suffice; do not imply public users can approve. |
| P2 | New V2 live-provider sample | Defer: it would sample availability/schema selection, not strengthen the deterministic boundary proof. No paid requests authorized or planned. |
| P2 | ATT&CK metadata | Defer: technique labels add less inspection value than the implemented predicates; no mappings or coverage claims added. |
| P2 | Broad property/fuzz framework | Use focused ordering/window regressions for the demonstrated weakness; add no dependency. |
| REJECT | New trace database/dashboard, public writes, signing/key management, new infrastructure | Disproportionate complexity or authority expansion. Preserve unsigned-manifest limits. |

## Bounded implementation and verification plan

1. Reuse one principal/first-alert-anchored partition and qualification decision in
   correlation and replay receipts. Exactly 30 minutes remains inclusive. Ties use
   rule and signal identity. Record a correlation policy identifier and actual
   constants; the detection ruleset digest alone does not identify that policy.
2. Render receipts only from reached frames. Show distinct rules and families,
   first/last alert times, span, configured requirements, incident outcome, and
   exact unmet conditions. Link existing completed hypothesis counterevidence;
   approval remains context, never an implicit correlation veto. Omit speculative
   counterfactuals and any claim that a historical window is currently active.
3. Link Atlas, approved administration, and the fixed APP-002
   `miss-service-access` comparison from the existing overview callout. Ignore
   invalid, repeated, or oversized selectors without sending arbitrary values to
   the API. No automatic replay or premature completed-evidence reveal.
4. Add focused tests for decision/case agreement, independent principals/windows,
   repeated rules, boundaries, equal-time permutations, reached-prefix display,
   and comparison selectors. Update only affected replay/workbench/demo/threat
   documentation, then run the full supported deterministic validation suite.
5. Review the diff and staged artifacts, scan secrets, commit meaningful changes,
   verify CI and production desktop/mobile behavior, and record fresh results.

Stop when positive and negative decisions are inspectable, the strongest path is
discoverable, provenance remains clear, and public safety and documentation are
verified. No additional features follow from this audit.
