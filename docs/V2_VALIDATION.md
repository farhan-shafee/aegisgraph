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
| Reachable Git history secret scan    | Gitleaks 8.30.1: 16 commits through the release push, zero leaks                            |
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

Release commit `559e3adfb525bec806c72556db69f22b2a96c91e` was pushed to `main`.
[GitHub Actions run 35892420786](https://github.com/farhan-shafee/aegisgraph/actions/runs/35892420786)
passed all three jobs: backend, frontend, and browser. Its logs independently
confirm 670 backend tests, 121 frontend tests, 20 local browser tests, six public
browser tests, 145 benchmark obligations, PostgreSQL clean initialization and
populated upgrade, dependency audits, and the Docker public readiness check.

Both application services deployed that exact release commit:

- Vercel production deployment `EM9QcQ6iSxHv15TWTnWegEf8TnGG`, recorded by GitHub
  deployment `6619656133`, succeeded at 16:58 UTC.
- Railway API deployment `58dd9191-4061-488b-ad7b-f0f012a0db48` succeeded; its public
  runtime advertised all six V2 capabilities and `/ready` returned 200.
- The existing PostgreSQL service, service configuration, variables, repository
  visibility, and domain were not changed. The existing predeploy command ran
  `public-init` without `--seed`.

Railway's initial redeploy action rebuilt the previous revision; commit metadata
identified that immediately. An explicit deployment of the latest connected
repository commit then deployed V2. During the staggered rollout, the new frontend
served the original case and hid unsupported V2 controls until capabilities were
available. No architecture or hosting-configuration workaround was needed.

Direct Railway-origin validation completed at 17:04 UTC: readiness and runtime
passed, seven invalid/nonexistent-target write probes returned 403, and `/docs`,
`/redoc`, and `/openapi.json` returned 404. The canonical incident response matched
the pre-V2 snapshot and remained unchanged after these probes. The saved PowerShell
snapshot had converted UTC timestamps to local offsets; comparison normalized
only equivalent ISO timestamp instants, preserving every other field and value.

Hosted browser verification completed at **17:11 UTC**. All ten planned check
categories passed across the bounded main run and a six-check continuation:
runtime, dashboard, scenario replay, canonical investigation, detection regression,
benchmark, architecture, mobile, proxy denials/docs, and unchanged canonical state.
This was not a single uninterrupted ten-check pass.

The canonical investigation showed evidence drawers, entity filtering, four
hypotheses, and a 35-file downloaded bundle verified VALID. The summary question
returned ten deterministic findings; the malware question returned insufficient
evidence and no findings. Both had zero validation errors. APP-002's 1,500-record
example computed PASS with the documented populations. The hosted benchmark
executed 145/145 obligations; filtering and expanded expected/observed values
worked. At 320 pixels, architecture, replay, evidence, entities, hypotheses, and
light-theme views had no horizontal overflow; reduced motion used manual stepping.
Five invalid/nonexistent-target writes through the frontend proxy returned 403,
and its docs/OpenAPI probes returned 404. There were no browser console/page
problems or unexpected application HTTP errors in the passing checks.

Two smoke-harness issues were retained and investigated. Chromium could not return
the cached network body for an export even though its download and visible VALID
state succeeded; the check now reads the bounded actual downloaded file. A later
benchmark assertion timed out and did not reproduce in a targeted probe or manual
browser inspection. The continuation explicitly observed a view transition before
filtering and passed all remaining checks without repeating analyst questions.
Observed canceled requests were Next.js RSC prefetches. No application change or
weakened assertion was needed to complete verification.

The canonical incident and hypothesis responses were byte-equivalent under sorted
JSON serialization before and after the live interactions, with combined SHA-256
`519f581d516714b911b9edca29165962f063b03df2a73cc58c28dfc56b1cb4b7`.
This is public API state evidence, not a privileged snapshot of every hosted
database table. The whole-database non-mutation check remains the dedicated local
PostgreSQL result above. Hosting variable names were inspected without retrieving
values; no OpenAI credential name was present on the API service.

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
