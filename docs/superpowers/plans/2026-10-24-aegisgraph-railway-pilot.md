# AegisGraph Railway frontend pilot implementation plan

> **Historical deployment context** - This record retains its original milestone, source revisions, measured results and approval boundaries. Earlier hosting/source-visibility/pending-release statements are dated history. Use [the current production documentation](../../DEPLOYMENT.md) for the October 24-25 Railway topology, release state and remaining closeout.

> For agentic workers: execute the approved plan inline with superpowers:executing-plans. Keep a ledger in .runtime/railway-pilot/progress.md.

Goal: patch the flagged frontend dependencies and prove an equivalent Railway frontend without switching the live domain.
Architecture: keep the existing Railway API and PostgreSQL, public-demo runtime contract, and Vercel frontend. Add one parallel web service; preserve the current trusted origin and add only the pilot's exact HTTPS origin after its hostname is known.
Tech stack: Node 24, Next.js, npm lockfile, existing FastAPI/PostgreSQL, Railway.
Spec: the user's approved three-step dependency-fix, isolated-pilot, parity-verification plan in the conversation on 2026-10-24.

## Global constraints
- Base main is f61618506d846844da46f18d86df7c6637231b9e.
- No main merge/push, production domain switch, database migration, reseed, or deletion.
- Keep APP_MODE=public_demo, the deterministic provider, exact origin validation, research caveats, and all UI behavior.
- Do not provide OpenAI credentials or make paid model calls.
- Do not perform persistent writes against hosted data.
- Deploy from the local isolated branch with Railway CLI; do not require a Git push.

## Review focus
- The temporary origin must support the two curated analyst requests without trusting arbitrary origins.
- Public mode and the HTTPS API contract must fail closed.
- Railway must bind 0.0.0.0 and preserve HSTS, CSP, no-store API behavior, and routing.
- Lockfile changes must resolve the reported advisories without upgrading unrelated application behavior.
- Existing hosted fixture rows and protected research semantics must remain unchanged.

## Task 1: dependency and compatibility patch
Files: apps/web/package.json, apps/web/package-lock.json, apps/web/next.config.ts if required for header parity.
- [ ] Establish clean baseline; record full npm audit and existing component tests.
- [ ] Reproduce the known dependency audit failure before changes.
- [ ] Pin next and eslint-config-next to the current fixed 16.4.3 release; update only affected sharp/source-map-js transitive dependencies as required.
- [ ] Preserve Vercel's measured HSTS max-age=63072000 in the Railway runtime.
- [ ] Run formatting, lint, type checks, full frontend tests, production build, and full npm audit.
- [ ] Run existing backend and local/public browser regression checks against disposable local data.
- [ ] Commit the bounded patch on the isolated branch.

## Task 2: parallel service and exact-origin integration
Consumes: tested local commit; produces: a temporary Railway HTTPS URL.
- [ ] Save current API origin settings and deployment identifiers.
- [ ] Create one isolated Railway frontend service in ample-adventure/production, rooted at apps/web, with Node 24.
- [ ] Use APP_MODE=public_demo and API_INTERNAL_URL=https://aegisgraph-api-production.up.railway.app.
- [ ] Build with npm ci / npm run build. Start node_modules/next/dist/bin/next with --hostname 0.0.0.0; use Railway PORT.
- [ ] Deploy local source with Railway CLI; require terminal SUCCESS and a healthy temporary hostname.
- [ ] Add only the exact pilot origin to ALLOWED_ORIGINS, preserving https://aegisgraph.farhan-shafee.com; redeploy the existing API artifact without source changes or --seed.

## Task 3: hosted parity and completion
Consumes: pilot URL plus bounded API origin allowlist.
- [ ] Compare the pilot and Vercel through representative read routes, all core views, security/cache headers, and desktop/mobile rendering.
- [ ] Exercise deterministic analyst, replay, fixed rule comparisons, hypothesis inspection, benchmark, and bundle verification within existing rate limits.
- [ ] Verify forbidden writes and untrusted origins fail; verify hosted data remains unchanged.
- [ ] Obtain one fresh whole-branch review; resolve material findings.
- [ ] Save a concrete acceptance report and leave production DNS/domain untouched for separate approval.
