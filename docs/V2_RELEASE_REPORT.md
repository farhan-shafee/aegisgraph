# AegisGraph V2 release report

Prepared 2026-09-23. Application implementation and local validation are complete;
CI and hosted rollout verification remain pending the release push. The
[validation record](V2_VALIDATION.md) separates observed local results from
hosted evidence.

1. **Initial architecture assessment.** The existing Next.js → FastAPI →
   PostgreSQL design already had strong deterministic detections, evidence scope,
   bounded provider output, and public write denial. The principal gaps were the
   single meaningful fixture, Git-only rule revisions, and missing comparative
   regression, hypothesis, and export workflows. The architecture was retained.
2. **Deliberately omitted.** No Kafka, Kubernetes, Elasticsearch, Neo4j, additional
   model provider, arbitrary rule editor, or autonomous remediation. Bounded
   deterministic projections fit the existing API; SSE/WebSockets would add
   state and transport complexity without improving this finite replay.
3. **Stale documentation.** README, deployment, system design, navigation, demo,
   and interview notes now describe the hosted Vercel/Railway topology and V2
   boundaries. Dated V1 release, public-demo preparation, and OpenAI records remain
   historical. Current results have their own linked record.
4. **Scenario corpus.** Eight versioned synthetic scenarios contain 4,098 events:
   Atlas compromise, authentication pressure, service access, enumeration,
   approved administration, bulk automation, isolated anomaly, and mixed context.
   Independent expectations are evaluator-only. Atlas IDs and original counts
   remain unchanged. See [corpus](../packages/synthetic-data/README.md).
5. **Replay architecture.** The server returns bounded causal JSON frames; the
   browser owns its cursor and Start/Pause/Resume/Step/Reset/speed controls.
   Prefixes contain only arrived evidence. Public replay creates no stored case,
   workflow row, or per-visitor server session. See [replay](REPLAY.md).
6. **Detection tuning and versioning.** Ten fixed rule definitions are inspectable;
   eight expose supported typed parameters. Local proposals, runs, and reviews are append-only. Approval
   independently recomputes the full-corpus result and rejects stale baselines;
   historical Atlas alerts are preserved. Public mode exposes three fixed
   APP-002 comparisons. See [workbench](DETECTION_WORKBENCH.md).
7. **Regression metric meaning.** TP/FN count required scenarios; FP/TN count
   explicitly benign scenarios. Other labeled scenarios participate in full-rule
   obligations and correlation gates without being misclassified as benign.
   APP-002 1,000 → 1,500 retains TP 2/FN 0 and changes FP 1 → 0, TN 1 → 2
   across two required and two benign scenarios; four other scenarios are
   separately reported. Required full-rule hits remain 26/26. PASS/WARN/BLOCK
   decisions list reasons. These are fixture counts, not population statistics.
8. **Hypothesis ledger.** Four evidence-derived hypothesis types separate support,
   narrow counterevidence, typed missing evidence, and human review. Conditional
   gap guidance invents no future fact. Context changes invalidate prior local
   review applicability. See [hypotheses](HYPOTHESES.md).
9. **AI evaluation expansion.** Version 1 of the V2 benchmark executes 145 named
   obligations with eight explicitly defined, overlapping metric populations.
   It tests schema, citations, support, insufficiency, isolation, containment,
   unsupported claims, and counterevidence. It calls no live model and does not
   replace the original 28-case record. See [benchmark](evaluations/BENCHMARK.md).
10. **Evidence bundles.** A scoped JSON container stores exact UTF-8 logical files
    and SHA-256 hashes from a bounded committed snapshot. Python and browser
    verifiers validate membership, bytes, and limits without extraction. Public
    bundles omit human workflow material. VALID/MODIFIED/MISSING FILE/UNEXPECTED
    FILE/INVALID describe verification results against an unsigned replaceable
    manifest. See [exports](EVIDENCE_BUNDLES.md).
11. **Security changes.** The updated [threat model](threat-model/THREAT_MODEL.md)
    covers replay/benchmark resource limits, answer-key separation, typed rule
    changes, recomputed regression gates, review context, export/parser/path
    boundaries, cross-case scope, public denial, and process-local abuse controls.
    Logs report bounded operation classes/counts/durations without sensitive
    payloads. No public model credential or mutation authority was added.
12. **Database migrations.** Additive 004 rule-state tables and 005 hypothesis
    review tables preserve populated V1 records. Fresh PostgreSQL initialization,
    idempotent upgrade, append-only controls, and usable post-upgrade local review
    were verified in dedicated databases. There was no hosted seed/reset request.
13. **API changes.** Versioned runtime capabilities advertise scenario catalog/replay,
    fixed scenario analysis, rule proposal/regression/review, hypothesis inspection
    and local review, deterministic benchmark, and scoped bundle export. Read
    surfaces stay bounded; central public mutation denial covers new paths. The
    existing two-question public analyst contract remains compatible.
14. **UI changes.** Restrained navigation adds Replay beside investigation,
    detections, evaluations, events, and architecture. Canonical cases gain
    Hypotheses and Export. The workbench displays typed parameter changes,
    scenario outcomes, computed gates, and explicit human review. Runtime
    capability checks support staggered frontend/backend rollout.
15. **Accessibility.** New controls have labels, textual statuses, keyboard/focus
    behavior, responsive layouts, reduced-motion manual playback, and light/dark
    support. Browser checks cover widths down to 320 pixels and high zoom. This
    is not a formal accessibility certification.
16. **Performance.** Recorded first/repeat measurements include scenario generation,
    replay, detection, correlation, PostgreSQL incident load/export, regression,
    verification, and benchmark execution. Full comparison was approximately
    2.96 seconds first / 2.77 seconds repeat median on this workstation. Cache and
    measurement limits are explicit in [validation](V2_VALIDATION.md#fixture-scale-timings).
17. **Backend tests.** 670 passed in the final full local run; Ruff lint/format
    passed. Two existing dependency deprecation warnings remain.
18. **Frontend tests.** 121 passed in 22 files. Prettier, ESLint, TypeScript, and
    production build passed.
19. **Browser tests.** 20 local and six public HTTPS tests passed, with retries
    disabled. Actual hosted smoke verification is tracked separately below.
20. **Evaluation counts.** Original suite 28/28; V2 benchmark 145/145. The 145
    cases and overlapping metric populations are not independent statistical
    samples or a claim of AI accuracy.
21. **CI status.** Pending release push. Three deterministic jobs validate backend,
    frontend, and browsers; PostgreSQL clean/populated migrations, Docker image,
    corpus/regression/export boundaries, build, and dependency audits are included.
    No live OpenAI calls or private key are required.
22. **Deployment status.** Pending V2 rollout verification. Existing Vercel Next.js,
    Railway FastAPI, and Railway PostgreSQL are retained. No new paid service,
    hosting configuration, repository visibility change, or public OpenAI key is
    part of this release.
23. **Public smoke results.** Local public production rehearsal passed all six
    browser tests and whole-database state-preservation checks. Actual hosted V2
    routes, mobile/console/network, two curated answers, denied writes, disabled
    docs, and canonical state comparison remain to be verified after deployment.
24. **Remaining limitations.** Synthetic fixtures and finite claim predicates;
    curated public language; unauthenticated local actor labels; no tenants or
    production ingestion; process-local limits/caches; no production performance
    or detection-effectiveness measurements; unsigned replaceable manifests;
    no source-truth, enterprise-readiness, or universal injection-resistance claim.
    Optional local OpenAI behavior retains the historical validation's scope.
25. **Commits.** The ordered implementation commits are recorded below. Phase 8
    documentation and final hosted verification commits will be identified in
    the delivery report after they exist.
26. **Working tree.** Phase 8 documentation/screenshots are awaiting the reviewed
    commit. Final delivery requires push confirmation and a clean working tree;
    this draft does not claim those steps have happened.

## Implementation commits

| Phase                       | Commit                                     |
| --------------------------- | ------------------------------------------ |
| 0: audit and plan           | `56bffc4131bb3ce08f08f0b83931a2ffb1a9e476` |
| 1: scenario corpus          | `9d4d07d279dd84f7c45f6c6352c3a1ecc5cb4971` |
| 2: causal replay            | `26784d43319d1b3ab6f4f2b0bb0fe8e3b48b4631` |
| 3: typed rule revisions     | `12b3ad6cd899c80f8b0163b3c2695b7c45f626c2` |
| 4: hypotheses               | `170fce1427c811d7680ceedceb3913960d49f33f` |
| Finding-capacity correction | `ddccab5877b3ef508a1c3b0d3544ccb90bcc0eef` |
| 5: analyst benchmark        | `0a55153a529cbd14172bc21cd996b1340fd4943b` |
| 6: evidence bundles         | `d46b49eae5ada6fbe4725e3b86f6cb48450bcbc7` |
| 7: integrated workflows     | `5c21a05c42cf5746a0b1148ff06fe07c5eeddca2` |

## Interview and site handoff

- [Seven-minute interview script](DEMO.md), including public and local alternatives.
- [Five résumé bullets, five project/LinkedIn bullets, and personal-site handoff](PERSONAL_SITE_HANDOFF.md).
- [Five reviewed real V2 screenshots](screenshots/README.md).

The personal-site repository was not modified.
