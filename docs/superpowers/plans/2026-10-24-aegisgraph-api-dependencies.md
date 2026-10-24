# AegisGraph API dependency remediation implementation plan

> For agentic workers: execute inline with superpowers:executing-plans; one fresh whole-branch review at the end.

Goal: resolve the four reported Python advisories with only two pin changes, verify compatibility, and deploy the API fix.
Architecture: retain the existing Railway API/Postgres, exact production+pilot origins, deterministic public mode and frontend pilot. Reuse the isolated worktree on a new branch based at961044e.
Tech stack: requirements.lock, Python3.13 Docker image, current Python test environment, PostgreSQL, Playwright, Railway.
Spec: user approved the certifi/filelock API remediation in this conversation on2026-10-24.

## Global constraints
- Change only certifi2026.7.22 to2026.10.19 and filelock3.32.7 to4.2.1 in requirements.lock, unless dependency resolution proves an additional change essential.
- No UI/API business logic, TLS-policy weakening, hosted database migration/reseed/delete, new hosted services, paid model calls, main merge/push or production-domain change.
- Keep public_demo, read_only and deterministic contracts and exact two-origin allowlist.
- Deploy the tested local source explicitly to the existing API service; retain rollback deployment4345a3a4-31bc-4861-a862-8c486aa79cff.
- Do not expose credentials. Snapshot hosted data through read-only transactions.

## Review focus
- The patched certifi bundle must retain valid HTTPS behavior without bypassing verification.
- Filelock4 must remain compatible with the installed audit/cache tooling and application regression suite.
- Deployed Linux/Python3.13 must actually contain the patched versions.
- Existing domain routes, both curated analyst questions, read-only denial and deterministic caveats must remain usable.
- Exact origin configuration and hosted table contents must remain unchanged; the live custom domain stays Vercel.

## Task1: bounded patch and compatibility proof
Consumes: base961044e and reproduced audit findings. Produces: tested local commit.
- [ ] Run full pip-audit against unchanged requirements; expect exit1 with four advisories in two packages.
- [ ] Modify the two exact pins and install the lockfile in the worktree environment; pip check must pass.
- [ ] Run full pip-audit again; expect0 advisories.
- [ ] Run ruff check/format and the full backend suite with dedicated local PostgreSQL and project-local basetemp; expect695pass.
- [ ] Build the actual Dockerfile, inspect installed versions/pip check, and public-check against disposable local PostgreSQL; expect success with no production credentials.
- [ ] Run existing local public HTTPS browser suite against dedicated initialized local data; expect7pass.
- [ ] Commit requirements.lock and this plan only.

## Task2: deploy and verify existing API
Consumes: Task1 commit. Produces: healthy API deployment on existing hostname.
- [ ] Capture fresh hosted read-only before snapshot; verify current API config/rollback info.
- [ ] Upload local source to existing APIe6a0d41d-cfeb-4d25-9daa-666e8eb2d8b5 in project97a3cf06-cbde-4c37-a24e-0b79cc857509/envc886fee6-6d6e-4355-91db-034905edc858. No seed or source auto-update.
- [ ] Require terminal SUCCESS, /ready200, public_init unchanged, and installed certifi/filelock versions verified inside the live container.
- [ ] Re-run hosted public suite on the existing frontend pilot plus security/origin checks and bounded Vercel compatibility checks; expect allpass.
- [ ] Compare hosted after snapshot with before; expect identical counts/hashes across22tables and migration005_hypothesis_workflow.
- [ ] Obtain one fresh whole-branch review, resolve material findings, and save a completion report.
- [ ] Preserve branch and prior deployment. Domain switch remains separate.
