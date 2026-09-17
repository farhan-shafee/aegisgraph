# Local setup and verification

[Project overview](../README.md) · [Documentation guide](README.md) ·
[Demo walkthrough](DEMO.md)

Requirements: Python 3.12+ and Node.js 24+. PostgreSQL 17 is the primary database;
the quickest local demonstration uses a reserved SQLite file. All commands run
from the repository root. No OpenAI key is needed for the ordinary demo or tests.

## Install

```sh
python -m venv .venv
```

Activate the environment:

```sh
# macOS/Linux
source .venv/bin/activate
```

```powershell
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
```

Then install the locked dependencies:

```sh
python -m pip install -r requirements.lock
python -m pip install -e . --no-deps
npm ci --prefix apps/web
```

## Credential-free SQLite demo

```sh
python -m aegisgraph.cli demo-reset
python -m aegisgraph.cli demo-api
```

Start the web application in a separate terminal:

```sh
npm run dev --prefix apps/web
```

Open [the workspace](http://127.0.0.1:3000) or
[API documentation](http://127.0.0.1:8000/docs). The Next.js server proxies `/api`
to the loopback API. Verify the running demo from an activated API terminal:

```sh
python -m aegisgraph.cli demo-health
```

This checks API/database availability, seeded counts, the primary incident,
evidence, deterministic fixtures, and a deterministic analyst response. It does
not call an external model.

For a production-built local frontend, replace `npm run dev` with:

```sh
npm run build --prefix apps/web
npm run start --prefix apps/web
```

## Reset behavior

Stop the API before running `demo-reset` again. It **deletes disposable demo
data**, including annotations, findings, approvals, and saved runs; then migrates,
seeds, detects, correlates, and runs deterministic evaluations.

The SQLite command targets only `.runtime/aegisgraph-demo.db` and ignores an
arbitrary `DATABASE_URL`. The matching `demo-api` command uses that database and
explicitly selects the deterministic provider by default, even when `.env`
selects OpenAI. Path and database guards are in
[`demo.py`](../apps/api/aegisgraph/demo.py). There is no HTTP reset endpoint.

## PostgreSQL

The [Compose file](../compose.yaml) binds PostgreSQL to loopback with deliberately
public demo credentials. They are not suitable for a real deployment.

```sh
docker compose up -d --wait postgres
alembic upgrade head
python -m aegisgraph.cli seed
python -m aegisgraph.cli evaluate
uvicorn aegisgraph.main:app --host 127.0.0.1 --port 8000
```

These ordinary commands honor `DATABASE_URL` and provider configuration, defaulting
to the Compose database and deterministic provider. They do not silently reset
an existing database. SQLite does not claim PostgreSQL type/concurrency parity.

For guarded PostgreSQL reset, create a separate reserved database once:

```sh
docker compose exec postgres createdb -U aegisgraph -O aegisgraph aegisgraph_demo
python -m aegisgraph.cli demo-reset --postgres-port 5432
python -m aegisgraph.cli demo-api --postgres-port 5432
```

Skip `createdb` if that reserved database already exists. For a native PostgreSQL
instance, create `aegisgraph_demo` with the local demo role/password from
[`.env.example`](../.env.example), then use its loopback port. The guarded commands
accept only that database name, demo role, and loopback host; they do not reset
the ordinary `aegisgraph` database or arbitrary hosts/names. Keep the native server
running while the API is in use.

## Configuration

The API loads the ignored repository `.env` without overriding process values or
interpolating its contents. [`.env.example`](../.env.example) contains safe
placeholders. Tests disable workstation `.env` loading. Never commit a local
environment file or expose credentials in screenshots/logs.

| Variable | Default / purpose |
|---|---|
| `DATABASE_URL` | Loopback PostgreSQL URL matching Compose; see `.env.example` |
| `AI_PROVIDER` | `deterministic`; `openai` explicitly opts into external calls |
| `AEGISGRAPH_LOAD_ENV` | `true`; use `false` to disable repository `.env` loading |
| `OPENAI_API_KEY` | Needed only for OpenAI mode; API process only |
| `OPENAI_MODEL` | Account-available model supporting Responses structured output |
| `API_INTERNAL_URL` | `http://127.0.0.1:8000`; Next.js server proxy target, set before build/start |
| `DEMO_ANALYST` | `demo.analyst`; an audit label, not authentication |
| `ALLOWED_ORIGINS` | `http://localhost:3000,http://127.0.0.1:3000`; mutation origins |
| `ALLOW_REMOTE_DEMO` | `false`; disabling the local-client guard does not add authentication |

Keep services local. AegisGraph does not implement public-deployment authentication
or tenant isolation. No API key is sent to the browser.

## Optional live provider

Configure the key and compatible model privately, then explicitly select live
mode for the reserved demo:

```sh
python -m aegisgraph.cli demo-api --provider openai
```

Add `--postgres-port 5432` when using the reserved PostgreSQL database. Live mode
sends bounded synthetic context to OpenAI and may incur charges. Failures display
explicitly; no silent deterministic fallback pretends to be a live answer.

The evaluation UI remains deterministic. The separate opt-in live runner and its
recording behavior are documented in [evaluation instructions](evaluations/README.md).
Historical results are in [live validation](evaluations/LIVE_VALIDATION.md).

## Testing

With dependencies installed, these checks need no API key or running database:

```sh
ruff check apps/api tests/backend scripts
ruff format --check apps/api tests/backend scripts
pytest -q
python -m aegisgraph.evaluations

npm run format:check --prefix apps/web
npm run lint --prefix apps/web
npm run typecheck --prefix apps/web
npm test --prefix apps/web
npm run build --prefix apps/web

pip-audit -r requirements.lock
npm audit --prefix apps/web --audit-level=moderate
```

Dependency audits need network access to their advisory services. Backend tests
use isolated databases and fixture/mock providers; deterministic evaluations run
without reading or changing application incidents.

Browser tests prepare a separate ignored SQLite database and start their own
loopback API/web servers on ports 8100/3100:

```sh
python scripts/prepare_e2e.py
node apps/web/node_modules/@playwright/test/cli.js install chromium
node apps/web/node_modules/@playwright/test/cli.js test --config playwright.config.ts
```

They do not reset the main demo database. On Linux, Playwright may need
`install --with-deps chromium` to install system browser libraries.

To mirror CI's PostgreSQL integration stage, use an isolated, disposable database
with `DATABASE_URL` set in the process environment and `.env` loading disabled
(`AEGISGRAPH_LOAD_ENV=false`), then run:

```sh
alembic upgrade head
python -m aegisgraph.cli seed
python -m aegisgraph.cli evaluate
python scripts/smoke.py
```

The [CI workflow](../.github/workflows/ci.yml) provisions a fresh PostgreSQL service
for these checks. It requires no private OpenAI credentials. See the dated
[validation record](VALIDATION.md) for actual results and environment limits.
