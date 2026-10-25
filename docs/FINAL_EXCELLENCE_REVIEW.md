# Final excellence review

> **Historical deployment context** - This record retains its original milestone, source revisions, measured results and approval boundaries. Earlier hosting/source-visibility/pending-release statements are dated history. Use [the current production documentation](DEPLOYMENT.md) for the October 24-25 Railway topology, release state and remaining closeout.

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

## Final audit results

Application revision: `72647c7ab40d82ea0a2ca73b206f1b554fd52497`.
Local validation completed on 2026-09-27 UTC. Results are a dated engineering
record, not continuous monitoring or a production security certification.

1. **Findings.** Two inspection gaps survived review: negative correlation was
   implicit, and the strongest three examples needed manual navigation. A latent
   equal-time ordering defect could change an incident ID for permuted input.
   These are addressed without changing the qualification thresholds or corpus.
2. **Already excellent.** Scoped evidence, typed claim/citation validation, human
   authority, full-corpus regression, bounded exports, public write denial, and
   candid architecture and evaluation documentation required no redesign.
3. **Candidates considered.** The decision table above records all candidates,
   including comparison, trace, review artifacts, live models, signing, ATT&CK,
   and additional property testing. Only P0/P1 work was implemented.
4. **Rejected expansion.** No new dashboard, database concept, detector, provider,
   signing key, queue, service, or public mutation capability was added.
5. **Decision receipts.** Each reached principal/window has exact counts,
   configured minimums, UTC bounds, outcome, matched signals, policy identifier,
   and unmet conditions. Approved administration reports 2/3 rules, 1/2 families,
   nine minutes, and no incident. Approval evidence remains separate context.
6. **Provenance.** Existing frames, source drawers, linked detections, incident
   evidence, hypothesis citations, and review/audit views already provide the
   chain. Receipts close its negative-decision gap; no parallel trace system.
7. **Guided demo.** Three links reuse the overview callout and existing routes.
   The APP-002 link selects the fixed 2,200-record BLOCK comparison. No popup,
   automatic playback, arbitrary threshold query, or extra navigation layer.
8. **Human-review proof.** Local browser tests exercise finding review, report
   approval, audit, export, and stale hypothesis review. Existing public images
   show an open review, not completed human approval. No new recording was needed;
   anonymous visitors remain unable to persist decisions.
9. **Live-provider evaluation.** Defer as P2. A new sample could measure current
   provider availability and claim selection, but does not replace deterministic
   support/citation tests. The historical record omits its model identifier and
   cannot reproduce a current V2 configuration. No paid requests occurred, and
   no live-model validation is claimed for this revision.
10. **Signing.** Keep exports unsigned. Hash agreement authenticates neither the
    manifest nor telemetry. No independent key trust/distribution/rotation need
    justifies a release-key system for this demonstration.
11. **ATT&CK.** No mappings added. A sparse technique catalog would add less value
    than inspecting the actual predicates; no technique coverage is claimed.
12. **Testing changes.** Added focused case/receipt agreement, rule repetition,
    principal isolation, disjoint-window and exact-boundary, time-zone, tied-input
    permutation, corpus-identity, reached-prefix, legacy fallback, and fixed-link
    tests. One public browser journey checks the guided near-miss/BLOCK path and
    canonical preservation. No fuzzing dependency was introduced.
13. **Implementation.** Shared `correlate_with_decisions`, additive replay
    receipts, deterministic tie-breaking, reached-state presentation, three
    overview links, and a bounded fixed comparison selector. Only affected replay,
    workbench, architecture, threat-model, and interview documentation changed.
14. **Security boundaries.** No migration, new endpoint, broader model context, or
    external model call. Public-mode PostgreSQL checks verified an identical
    whole-database snapshot after reads, fixed deterministic analysis, and denied
    writes. Existing backend/proxy denial and stale-review controls passed.
15. **Performance.** Atlas projection grows from 82,822 to 88,801 UTF-8 bytes
    (5,979 receipt bytes), below the unchanged 1 MiB cap; all eight scenarios stay
    bounded. Five alternating local samples gave an uncached Atlas median of
    approximately 1.33 seconds before and 1.30 after. This difference is noise
    under concurrent validation, not a speedup or hosted latency claim. No new
    network round trip is needed for a receipt.
16. **Accessibility.** Semantic receipt regions, labeled details and existing
    keyboard controls remain available. Browser checks cover 320, 375, 430, 768,
    1,280, 1,440 and 1,920 pixels, light theme, zoom, and keyboard behavior. The
    first local run found a five-pixel overview overflow at 320px; a scoped link
    wrapping fix made the unchanged complete suite pass. Manual receipt inspection
    at 320px showed no page overflow. This is not a formal accessibility audit.
17. **Exact local validation.** See the executed table below. Tests ran with local
    environment loading disabled and the deterministic provider selected.
18. **CI.** [Application CI](https://github.com/farhan-shafee/aegisgraph/actions/runs/36347642882)
    passed all three required jobs (backend, frontend, browser) for this exact
    revision. This includes the Linux Docker image check. No earlier release's
    green run is treated as evidence for these changes.
19. **Production.** Initial desktop/mobile inspection covered overview, replay,
    canonical timeline/evidence/entities/hypotheses, APP-002 BLOCK, evaluations,
    architecture, and export controls. The frontend deployment succeeded. The
    three published overview links and direct APP-002 BLOCK link were verified.
    A separate credential-free frontend smoke passed at 1,440 and 320 pixels with
    no page errors, no unexpected outbound origin, and no writes. Railway still serves application
    revision `559e3adfb525bec806c72556db69f22b2a96c91e` from deployment
    `58dd9191-4061-488b-ad7b-f0f012a0db48`. API deployment awaits operator
    authorization; the complete postdeployment smoke has therefore not run. Do
    not treat local receipts as proof that the hosted API has them. The prepared
    smoke compares the canonical incident and hypotheses against a predeployment
    snapshot; unlike local PostgreSQL validation, it cannot inspect every hosted
    database table.
20. **Commits.** `72647c7ab40d82ea0a2ca73b206f1b554fd52497` contains the bounded
    implementation and was pushed to `main`. This record is finalized separately
    so it can reference the tested application revision.
21. **Repository state.** The application commit was pushed with a clean working
    tree. Final report changes receive a separate documentation commit. Generated browser output,
    local databases, environment files, and downloads stay ignored and untracked.

### Executed local validation

| Check | Result |
| --- | --- |
| Backend | 695 passed; two existing dependency deprecation warnings; 265.31 seconds |
| Frontend | 129 passed in 22 files |
| Local browser | 20 passed; retries disabled; complete rerun after the 320px fix |
| Public HTTPS browser | 7 passed; retries disabled; production build and PostgreSQL |
| Original deterministic evaluations | 28/28 passed |
| V2 deterministic benchmark | 145/145 passed |
| Python formatting/lint | Ruff passed; 75 files formatted |
| Frontend formatting/lint/types | Prettier, ESLint, Next type generation and TypeScript passed |
| Production build | Local and public configurations passed |
| PostgreSQL | 17.10; fresh public initialization and whole-state preservation passed |
| Populated upgrade | V1 through additive V2 migrations, repeat upgrade and append-only guards passed |
| Scenario/regression/bundle validation | Included in the complete backend, frontend and browser suites; all eight scenario IDs preserved |
| Dependency audits | 55 Python packages and 553 npm dependencies; zero known vulnerabilities |
| Secret scans | Redacted reachable history: 18 commits through the application revision, zero leaks; staged implementation diff: zero leaks |
| Artifact/link review | No unexpected sensitive/generated staged paths; 263 repository paths reviewed; zero broken local Markdown links |

No Python static type checker is configured; the typecheck above is TypeScript.
The workstation used native PostgreSQL and installed Chrome; CI additionally
checks the Docker image on Linux. The historical additional 40-case cross-language
bundle experiment was not repeated or counted as a new result.

### Hiring-panel self-review and stopping point

| Perspective | Strongest proof | Remaining limit / likely interview question |
| --- | --- | --- |
| Detection engineer | Positive and negative receipts, labeled full-corpus gates | Why anchored disjoint windows, and what real traffic would challenge these thresholds? |
| Platform engineer | Independent public denials, immutable workflow records, committed export snapshot | How would authenticated tenants, retention and independent audit storage change the design? |
| AI/security engineer | Exact typed claims, independent support/citation predicates, adversarial fixtures | What can a valid but incomplete provider answer still omit, and how would model drift be measured? |
| Five-minute hiring manager | Three direct examples make one inspectable argument | Synthetic fixtures and local reviewer labels demonstrate engineering, not production efficacy or authenticated review. |

The remaining limits are explicit scope decisions. Once the deployment evidence
is recorded, freeze this scope; more features are not needed to strengthen it.

**Release state: implementation validated; Railway API deployment and complete
hosted smoke pending authorization.** No paid-provider requests were made.
