# Validation record

Local hardening validation date: 2026-09-17 UTC. Dataset date: 2026-09-15 UTC.
Results here describe this implementation run, not continuous operational metrics.
The later public-demo implementation has a separate
[validation record](PUBLIC_DEMO_VALIDATION.md); historical counts below are retained.

## Environment and persisted data

- Windows, Python 3.14.7, Node.js 26.8.2.
- Real PostgreSQL 17.10 on loopback, plus isolated SQLite test databases.
- The Docker CLI was available but the Docker engine was unavailable. PostgreSQL
  validation used an isolated native cluster under ignored `.runtime/` instead;
  the Compose startup itself was not exercised locally.
- A clean database was migrated and seeded: **4,026 events, 10 alerts, 1 incident,
  26 incident evidence items, 10 detection definitions**.
- The reserved PostgreSQL database `aegisgraph_demo` was created separately from
  the original database. Guarded reset, migrations, seed, detections, correlation
  and deterministic evaluations passed there and in the reserved SQLite demo.
  The case spans 22 minutes of alerts from nine distinct rules and five families.
- The schema has 15 application tables plus Alembic revision metadata. Ordinary
  event and audit UPDATE/DELETE operations were verified to fail in PostgreSQL
  and SQLite. Database-owner/DDL bypass is outside that guarantee.

## Backend and AI results

| Check | Executed result |
|---|---|
| Ruff lint | Passed |
| Ruff formatting | Passed |
| Backend and AI pytest | **146 passed**, zero failures |
| PostgreSQL clean migrations and seed | Passed |
| SQLite clean migrations, seed and guarded reserved reset | Passed |
| API/database smoke | Passed: health, counts, pagination, case graph/evidence, validation errors |
| Demo health command | Seven checks passed; no external provider called |
| Deterministic evaluation suite | 28 passed, 0 failed |
| Pinned Python dependency audit | No known vulnerabilities reported |
| Live deterministic analyst HTTP requests | Grounded answer and malware insufficient-evidence response verified |

Two upstream TestClient deprecation warnings were emitted (the HTTPX TestClient
adapter and AnyIO BlockingPortal alias). They did not fail tests. There is no
configured Python static type checker; no type-checking result is implied.

Full offline validation used `AEGISGRAPH_LOAD_ENV=false` and
`AI_PROVIDER=deterministic`. Ruff checked 31 Python files. Four ordinary PostgreSQL
event/audit UPDATE/DELETE attempts were blocked and rolled back in the reserved
database; 4,026 events remained. Tests also cover environment precedence, disabled
interpolation, guarded reset targets, file links, malformed health URLs and
separation of deterministic/live result retrieval.

## Live OpenAI results

| Check | Executed result |
|---|---|
| Latest named live scenarios | **Three passed out of three**: grounded investigation, malware false premise and projected malicious telemetry fixture |
| Harness external requests | Six attempted: three HTTP 200 successes and three earlier HTTP 429 failures |
| Local checks bundled with live report | **Five passed out of five**, separately labeled application-boundary execution |
| Additional production-browser live calls | Grounded answer and malware insufficient-evidence response both HTTP 200; no validation errors |

The harness and browser checks are separate: eight external requests total,
five successful HTTP responses and three HTTP 429 responses. The underlying
cause of HTTP 429 was not confirmed. Earlier failures remain recorded; latest
scenario success does not imply every request succeeded.

The injection fixture's free text was excluded before the external call. This
validates projection/output boundaries, not model resistance to instructions it
actually received. Exact configured model values, credentials, headers and raw
provider prose are omitted. See [live validation](evaluations/LIVE_VALIDATION.md)
and [sanitized attempt history](evaluations/live-attempts.json).

## Frontend and browser results

| Check | Executed result |
|---|---|
| npm install with lockfile | Passed |
| ESLint | Passed, no warnings |
| TypeScript | Passed |
| Prettier formatting | Passed |
| Vitest component/unit tests | **23 passed**, including retained provider-failure history after latest-case success |
| Next.js production build | Passed |
| npm dependency audit | 0 known vulnerabilities reported |
| Playwright suite | **13 passed**, 0 failed, retries disabled |
| Browser investigation workflow | Passed: source inspection, annotation, graph selection/filtering, analyst citations, false premise, finding approval, incident update, report approval/download and audit |
| Event filtering and evaluation UI | Passed against the running API |
| Responsive route matrix | Passed at 320, 375, 430, 768, 1280, 1440 and 1920 pixels |
| Production browser smoke | 8 routes passed against PostgreSQL; no page/console errors, HTTP failures or unexpected request failures |

The final production follow-up trace recorded 86 navigation-canceled React
Server Component requests and zero unexpected failures. Those cancellations are
distinguished from HTTP failures; this record does not claim that no browser
request was ever canceled.

Responsive checks covered all eight primary routes and the entity graph view.
Intentional table scroll containers are allowed; document-level overflow was
absent. Desktop and mobile screenshots were visually inspected. Keyboard tests
cover tab navigation, accessible panel naming, and evidence-dialog dismissal.
Dark/light themes and tablet/mobile captures were inspected. Grounded and
insufficient-evidence views were also confirmed using live provider responses
through the production-built browser application.
Light-theme route checks covered 390, 768 and 1440 pixels and verified persistence
after navigation and reload. Final inspection corrected the closed mobile
navigation drawer's visible shadow and verified its open/close behavior.

Browser execution used fresh Playwright Chrome contexts. The agent-browser helper
could not launch reliably in this Windows sandbox. Playwright's automatic server
teardown also hung in the sandbox; local execution instead used dedicated
manually managed test servers and `E2E_REUSE_SERVERS=1`. This only changes process
ownership, not assertions or the isolated test database. CI retains automatic
server management on Linux. An initially ambiguous device/session test locator
was made exact before the successful workflow run; retries remain disabled.
A later rerun initially reused the previously mutated E2E database and timed out
waiting for the first-time report-generation button. Re-running the documented
isolated database preparation restored the clean fixture before the final suite.

## Review scope

The implementation was reviewed for environment-secret handling, ignored local
data, unsafe dynamic execution, ORM binding, untrusted HTML rendering, incident
evidence scoping, origin/host controls, body limits, model context, report approval
metadata and stale-state handling. The model has no mutation tool interface.
The final file review checked 144 tracked or intended files against configured
secret values and key/private-key patterns, with zero matches. All local Markdown
links resolved. The ignored `.env`, databases, runtime tools and build outputs
were excluded from the commit; the public `.env.example` template contains no
local configuration values.

This is an engineering verification record, not a penetration test, security
certification, production readiness review, or proof that dependencies are free
from undisclosed vulnerabilities. CI configuration is versioned in
`.github/workflows/ci.yml`; hosted run status is reported separately after push.

The initial implementation commit `3764a742f89139813cf4e429d33bad325087b907`
passed all three hosted GitHub Actions jobs, including ten browser tests in that
earlier version. The hardening commit `7293c515d47178405df6fcf93feeeadac067cf64`
also passed [all three hosted jobs](https://github.com/farhan-shafee/aegisgraph/actions/runs/35176511095),
with 146 backend tests, 23 frontend tests and 13 browser tests. This document
records that historical hardening run; the newer [public release review](PUBLIC_RELEASE_REVIEW.md)
records fresh validation and any changed counts for release preparation.
