# AegisGraph V2 implementation plan

Planned 2026-09-20 against `1670ca4`. This is an engineering work plan, not a
validation or capability claim. Completed results belong in the V2 validation record.

## Assessment

The existing Next.js → FastAPI → PostgreSQL system already has deterministic
normalization, ten evidence-backed rules, principal/time/family correlation,
case-scoped evidence, an inspectable relational graph, typed provider output,
independent citation/claim validation, and separate human review. Public mode
centrally denies persistent writes and explicitly uses a deterministic provider.
The hosted Atlas investigation and curated analyst flow are accessible.

The principal weaknesses are one-fixture assumptions in readiness and the UI,
Git-only rule versions, no comparative scenario regression, and no explicit
hypothesis or export model. Replacing the database, introducing a broker, or
adding model providers would not address these gaps.

## Architecture and contracts

- Preserve the canonical hosted Atlas dataset and its identifiers. Add a versioned
  code-backed synthetic corpus with evaluator-only labels in a separate module.
  Runtime analyst context contains observations, never the answer key.
- Reuse pure detection/correlation functions. Replay returns bounded JSON computed
  from ordered telemetry prefixes; the browser owns only its playback cursor.
  No public database writes, per-visitor server sessions, SSE, or WebSocket service.
  The existing proxy is bounded JSON; streaming would add an unnecessary boundary.
- Store local rule proposals, immutable parameter snapshots, regression results,
  reviews, and hypotheses relationally through additive migrations. Allow only
  effective typed parameters. Recompute full-corpus gates before approval and
  reject stale base versions. Public examples use predefined proposals.
- Keep hypothesis epistemic status separate from human review. Validate support,
  contradiction, and finding references within the incident. Gap guidance uses
  typed evidence categories, not invented future observations.
- Expand deterministic analyst tests with independent expected outcomes. Version
  benchmark records so the historical 28-case hosted run remains identifiable
  and does not accidentally fail deployment readiness.
- Export a bounded JSON container of fixed logical files and SHA-256 hashes.
  Verification checks exact contents and file membership without extracting paths.
  An unsigned, replaceable manifest proves neither authenticity nor source truth.
- Keep current two public analyst questions compatible during staggered rollout.
  Expose hypothesis gaps through a separate read route. Preserve centralized write
  denial, explicit deterministic providers, bounded work, safe logs and Docker
  allowlisting. No new service, key, or hosting configuration is planned.

## Ordered phases and review gates

1. **Phase 0 — audit/current docs.** Inspect domain, AI, boundaries, UI, CI and live
   site; correct operational hosting language; preserve historical records.
2. **Phase 1 — corpus.** Implement eight scenarios: Atlas, authentication pressure,
   service-principal access, enumeration, approved administration, bulk automation,
   isolated anomaly, mixed context. Fix independently specified detections,
   non-detections, correlation, evidence categories and claim limits. Verify stable
   generation, IDs/order, unchanged Atlas, isolation and ground-truth separation.
3. **Phase 2 — replay.** Compute causal frames, no future evidence or incident before
   threshold, deterministic prefix/batch agreement, bounded response/cache/work.
4. **Phase 3 — detection workbench.** Typed rule snapshots and local review;
   before/after corpus results; explicit PASS/WARN/BLOCK reasons; immutable version
   and stale-review tests. Describe TP/FP/FN only as synthetic scenario measurements.
5. **Phase 4 — hypotheses.** Evidence-derived proposals and typed gaps; local human
   persistence/review, provenance and report invalidation; cross-case tests.
6. **Phase 5 — analyst benchmark.** Meaningful question/scenario and validator cases,
   including contradictory context, false premises, injection, malformed output,
   context bounds and foreign citations. Required execution never calls OpenAI.
7. **Phase 6 — export.** Case-scoped deterministic bundle and bounded verifier;
   valid/modified/missing/unexpected results and precise limitations.
8. **Phase 7 — UI.** Integrate scenario selection, playback controls, hypothesis
   ledger, typed tuning/diff/gates and local bundle verification. Retain the current
   editorial style. Exercise keyboard, reduced motion, 320px, zoom and both themes.
9. **Phase 8 — release validation.** Threat model/ADRs/docs, real screenshots,
   seven-minute demo and personal-site handoff; fixture timings; complete backend,
   frontend, browser, build, audit, secret and PostgreSQL clean/populated-upgrade
   checks. Review the entire diff, push main, verify CI/deployment and live behavior.

Each phase is inspected, implemented, tested and reviewed before a logical commit.
Tests for new behavioral contracts precede implementation. Independent tasks may
run in parallel within a phase, but future phases do not start prematurely. Push
only after the implementation and full local validation are complete. Production
availability and state-preservation results require actual deployment checks;
local tests alone are not presented as hosted verification.
