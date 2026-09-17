# Public demo preparation validation

Validated **2026-09-17 UTC**. This records preparation of the explicit
`APP_MODE=public_demo` implementation. **No Vercel or Railway deployment was
performed, and repository visibility/settings were not changed.** Follow the
[deployment runbook](DEPLOYMENT.md) for configuration and manual deployment.

## Executed checks

| Check | Result |
|---|---|
| Backend pytest suite | **224 passed** |
| Frontend Vitest suite | **35 passed**, 11 files |
| Local/interview Playwright suite | **13 passed** |
| Public production-build HTTPS Playwright suite | **3 passed** |
| Deterministic evaluation fixtures | **28/28 passed**, no external provider |
| Backend Ruff lint / formatting | Passed, 36 Python files |
| Frontend formatting / ESLint / TypeScript | Passed |
| Next.js production build in public mode | Passed without a running backend or credentials |
| Clean PostgreSQL migration, seed and public integration | Passed on PostgreSQL 17.10 |
| Python locked-dependency audit | No known vulnerabilities reported |
| npm dependency audit | Zero vulnerabilities reported |
| Git whitespace/error check | Passed |

The local environment used Windows, Python 3.14.7, Node.js 26.8.2, and Chrome via
Playwright. CI uses Linux, Python 3.13, Node.js 24, PostgreSQL 17, and Chromium.
The two existing Starlette/AnyIO test deprecation warnings remain; they are not
test failures. The Docker engine was unavailable locally. CI additionally builds
the actual Railway image and runs its public dataset check against PostgreSQL;
consult the [commit's Actions run](https://github.com/farhan-shafee/aegisgraph/actions/workflows/ci.yml)
for that container result. Hosted ingress, certificates, Vercel/Railway wiring,
and platform healthcheck activation still require the manual hosted smoke check.

## Database and persistence evidence

[validate_public_database.py](../scripts/validate_public_database.py) ran against
a newly created, dedicated PostgreSQL database after the final readiness changes:

1. Alembic migrated the empty database to head. Initialization without `--seed`
   left it empty and not ready.
2. Explicit initialization produced 4,026 events, 10 alerts, one flagship incident,
   26 evidence items, 235 total entities, and one passing deterministic evaluation.
3. Reinitialization with and without `--seed` returned `unchanged`.
4. Read routes, the flagship, both curated questions, and blocked write requests
   were exercised against that actual PostgreSQL database.
5. A snapshot of **every application table** was identical before and after the
   repeated initialization and public requests. No analysis or audit row was saved.

The original interview databases were preserved. Initialization tests also cover
local incident/evidence edits, unexpected audit entries, partial datasets, missing
evaluation recovery, concurrent initialization lock contention, and lock release
on failures. Readiness rejects edited/local saved work; it is a fixture check,
not a cryptographic integrity attestation. No schema migration was added by this
deployment preparation.

## Public boundaries and retained experience

Backend tests cover remote read access, exact HTTPS origins and hosts, safe input
errors, disabled API docs, bounded body/URL/header sizes, fixed-memory shared
rate/concurrency limits, and ignored spoofed forwarding headers. Nineteen write
route/method cases are denied, including unknown reset/admin routes. The only
allowed application POST is a curated, non-persistent analyst request.

The public provider is explicitly deterministic even when `AI_PROVIDER=openai`
is configured and no key is present. Tests verify evidence-reference membership,
grounded answers, insufficient evidence for the malware-family question, and no
stored analysis/audit rows. The real OpenAI integration remains available in local
mode; no live OpenAI request was made during this validation. Its earlier measured
results remain in [LIVE_VALIDATION.md](evaluations/LIVE_VALIDATION.md).

Public browser tests used the **production Next.js build** with a real FastAPI
process, PostgreSQL, and local HTTPS proxies. They exercised all eight primary
routes, source-evidence drawers, entity selection, both analyst questions, citation
navigation, read-only controls, blocked proxy writes, and the evaluation results.
The local suite separately retained annotations, findings, report approval,
evaluation execution, and responsive dark/light route checks.

## Secret and artifact inspection

- Gitleaks 8.30.1 scanned all four pre-change commits with full redaction: no leaks.
  The release diff is also scanned before commit; no allowlist suppression is used.
- Source and documentation are checked against configured secret values in memory,
  without printing those values. Relative documentation links are checked.
- All 17 production client files were checked for configured secrets, the private
  workspace path, database-connection schemes, and configured/default backend
  addresses: no matches. There are **no `NEXT_PUBLIC_*` uses** in web source.
- The Next.js server-only boundary and client props were reviewed. The proxy does
  not forward Authorization, cookies, or client forwarding headers. Public API
  error tests verify that connection/error markers and submitted values are not
  returned. API request logs omit paths, headers, and body values.
- Staging is limited to reviewed source, tests, documentation, and deployment
  configuration. `.env`, databases, generated TLS keys/certificates, `.runtime`,
  build output, browser reports, and screenshots from test failures remain ignored.
- Existing reviewed repository screenshots were unchanged; no new screenshot was
  added to the public documentation by this change.

These scans are bounded checks, not a guarantee that no secret or vulnerability
could exist. The earlier source/history/image review remains separately scoped in
[PUBLIC_RELEASE_REVIEW.md](PUBLIC_RELEASE_REVIEW.md).

## Remaining deployment decisions

The code is prepared for a small synthetic read-only demonstration. The owner
must still provision the services, choose exact domains, supply private database
configuration, deliberately initialize the fixture, pass `/ready`, and perform
the hosted smoke steps before sharing a URL. Keep one API worker/replica; limits
are process-wide, reset on restart, and provide no per-visitor fairness or DDoS
guarantee. Configure hosting budgets, monitoring, and backups. Separate least-
privilege database roles, real authentication/tenant isolation, production data
handling, and scale/availability guarantees remain future production work.
