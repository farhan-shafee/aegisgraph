# AegisGraph V2 validation

Local validation completed **2026-09-23 UTC**, against application commit
`5c21a05c42cf5746a0b1148ff06fe07c5eeddca2`. Phase 8 adds documentation,
reviewed screenshots, their capture utility, and the populated-upgrade CI step.
This is a dated engineering record, not a continuous monitoring claim.

## Executed checks

| Check                                | Result                                                                                      |
| ------------------------------------ | ------------------------------------------------------------------------------------------- |
| Backend pytest                       | **670 passed**, two existing dependency deprecation warnings, 310.16 seconds                |
| Python lint / formatting             | Ruff clean; 74 files already formatted                                                      |
| Frontend Vitest                      | **121 passed** in 22 files                                                                  |
| Frontend formatting / lint / types   | Prettier, ESLint, `next typegen && tsc --noEmit` passed                                     |
| Local browser suite                  | **20 passed**, retries disabled, 1.6 minutes                                                |
| Public HTTPS browser suite           | **6 passed**, retries disabled, 13.6 seconds                                                |
| Original deterministic evaluation    | **28/28 passed**                                                                            |
| V2 deterministic benchmark           | **145/145 passed**                                                                          |
| Next.js production build             | Passed, including public configuration                                                      |
| PostgreSQL clean initialization      | Passed on PostgreSQL 17.10                                                                  |
| PostgreSQL populated V1 → V2 upgrade | Passed, preserving V1 state                                                                 |
| Dependency audits                    | `pip-audit -r requirements.lock`: no known vulnerabilities; npm audit: zero vulnerabilities |
| Reachable Git history secret scan    | Gitleaks 8.30.1: 15 commits scanned before the Phase 8 commit, zero leaks                   |
| Browser / Python bundle parity       | 40 valid and hostile cases agreed                                                           |

The Windows workstation used Python 3.14.7, Node.js 26.9.0, native PostgreSQL
17.10, and installed Chrome through `PLAYWRIGHT_CHANNEL=chrome`. CI uses Python
3.13, Node.js 24, PostgreSQL 17, and Playwright Chromium. There is no configured
Python static type checker; the typecheck result above is TypeScript.

Required checks explicitly disabled local environment loading and selected the
deterministic provider. No OpenAI key or live model call was used. Historical
[live OpenAI validation](evaluations/LIVE_VALIDATION.md) is separate evidence.

## What the checks establish

- Eight deterministic scenarios contain 4,098 events. Atlas retains 4,026 events,
  10 alerts, one canonical incident, and 26 evidence items. Corpus labels remain
  separate from the runtime analyst projection.
- Replay verifies ordered telemetry prefixes, threshold timing, no future evidence,
  deterministic completed results, and bounded work. Atlas has 91 playback frames;
  the first correlated incident appears at 14:03 in fixture time.
- Typed local proposals, full-corpus comparisons, immutable reviews, stale-base
  rejection, independently recomputed approval gates, and public write denials
  are covered. APP-002 1,000 → 1,500 passes on the fixtures; 2,200 blocks.
- Hypothesis support, counterevidence, conditional gaps, scope isolation, context
  invalidation, and the separation of human review from evidence status are covered.
- The 145 named benchmark obligations cover eight overlapping metric populations.
  Their denominators must not be added together or described as model accuracy.
- Exports use a bounded committed snapshot. Tests cover exact bytes and membership,
  malformed containers, scope isolation, parser limits, unsafe names, database
  preflight bounds, and public omission of human workflow material. Browser and
  Python verification agree on 40 additional valid/hostile examples.
- Local browser tests exercise the complete investigation workflow, replay controls,
  completed-scope questions, hypothesis review and stale context, actual bundle
  downloads and local verification, PASS approval, BLOCK denial, and WARN review.
  Public browser tests inspect the fixed comparisons, benchmark, hypotheses,
  ephemeral replay, export, and intentional 403 responses on new write routes.
- Responsive checks cover 320, 375, 430, 768, 1,280, 1,440, and 1,920 pixels,
  selected light-theme widths, keyboard controls, visible focus, reduced motion,
  and high zoom. This is exercised coverage, not an accessibility certification.

## Database preservation

Two dedicated PostgreSQL databases isolated validation from existing local data.
The clean public check migrated, explicitly seeded, and reinitialized the fixture,
then exercised read routes, deterministic questions, and mutation denials. Its
whole-database snapshot was identical before and after public interactions.

The populated-upgrade check began at migration 003 with canonical records, notes,
reports, audit history, and evaluations. Additive migrations 004 and 005 preserved
those records, created empty V2 tables, and were idempotent. Local rule and
hypothesis reviews remained usable. Export used a read-only repeatable-read
PostgreSQL snapshot, a subsequent ordinary pooled write still worked, and SQL
append-only controls remained enforced. No original user database was reset.

The API smoke check reported 4,026 events, 10 alerts, one incident, and 26 evidence
items. Docker was unavailable locally; the CI backend job builds the actual API
image and runs its public readiness check against PostgreSQL.

## Reproduction and resolved test obstacles

Use [setup](SETUP.md) and the commands in [CI](../.github/workflows/ci.yml).
The standalone PostgreSQL scripts require dedicated disposable databases:

```sh
python scripts/validate_public_database.py
python scripts/validate_populated_upgrade.py
python -m aegisgraph.cli evaluate
python -m aegisgraph.cli evaluate-benchmark
```

On this Windows machine, the default pytest temporary directory was inaccessible.
The complete passing run used a fresh repository-local `--basetemp` and
`-o cache_dir` beneath ignored `.runtime/`. The first browser launch could not find
downloaded Chromium; the complete passing runs used installed Chrome. These were
environment failures, not silently skipped tests. A browser run also found that
the benchmark UI treated structured expected/actual values as strings; the
renderer and regression test were corrected before the fresh full browser run.

## Fixture-scale timings

Measured at **2026-09-23 16:50 UTC** on one uncontrolled development workstation,
using one first call followed by three immediate repeats in one Python process.
PostgreSQL was on loopback. No load generator was used. Values are milliseconds;
these are not production latency percentiles or scalability measurements.

| Operation                                           | First call | Median of three repeats |
| --------------------------------------------------- | ---------: | ----------------------: |
| Generate eight scenarios / 4,098 events             |     312.59 |                   95.85 |
| Detect all 4,098 events                             |   1,296.36 |                1,378.52 |
| Correlate eight scenarios, signals already computed |       1.92 |                    1.80 |
| Build Atlas replay, bypassing replay-result cache   |   1,685.29 |                1,519.45 |
| Full-corpus APP-002 1,000 → 1,500 comparison        |   2,961.96 |                2,770.01 |
| Load stored incident from PostgreSQL                |     138.89 |                   15.37 |
| Export public PostgreSQL case, 35 logical files     |      33.01 |                   24.14 |
| Python verification of parsed bundle                |       0.92 |                    0.74 |
| Execute 145-case benchmark, bypassing result cache  |   1,545.68 |                   83.52 |

Scenario caches can be warm during replay measurements. The benchmark's internal
scenario/replay caches warm on repeats even though its final-result cache is
bypassed. These numbers do not justify introducing a broker, graph database, or
distributed replay service.

## Artifact review

Five [V2 screenshots](screenshots/README.md) were captured from actual application
states in a local public-mode production rehearsal and individually inspected.
Only synthetic application data is visible; no keys, authorization headers,
private paths, real-owner usernames, machine details, or unrelated browser content
appear. The capture utility allows same-origin reads only, validates displayed
results, and checks the canonical case before and after capture.

Gitleaks and the local configured-secret-value scan print no secret values.
Environment files, databases, runtime output, dependency folders, browser reports,
and temporary certificates remain ignored. The standard MIT license names
Farhan Shafee, 2026. No visibility or repository-setting change is part of V2.

## Hosted verification

Local validation is complete. Verification of the V2 GitHub Actions run, deployed
revisions, and actual hosted interactions is pending the release push. This
section will be updated with observed results, not inferred from local tests.

## Limits

Public data is intentionally readable and synthetic. Local actor labels are not
authenticated identities. There is no tenant isolation, production ingestion,
autonomous response, or measured real-world detection effectiveness. Rate limits
and caches are process-local; platform-wide abuse controls and production capacity
remain operational work. Finite typed predicates and curated wording do not prove
general semantic correctness or universal prompt-injection resistance. An unsigned
bundle manifest can be replaced along with its contents; matching hashes prove
neither authorship nor source truth. See the [threat model](threat-model/THREAT_MODEL.md)
and [release report](V2_RELEASE_REPORT.md).
