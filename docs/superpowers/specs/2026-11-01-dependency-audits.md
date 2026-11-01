# Dependency audit repair

The routing PR's first CI run passed functional tests but failed both dependency
security gates: Python's msgpack 1.2.2 and minimatch versions below 11.0.1 in the
frontend lint dependency tree.

## Changes

- Pin msgpack to 1.2.3, the patched release for CVE-2026-114613.
- Override transitive minimatch dependencies to the upstream registry package
  11.0.1, the patched release for GHSA-g3hv-75wg-m249. Keep its registry integrity
  hash and remove older installed copies. Keep both audit gates enabled.
- Run the existing ESLint configuration through a Node 24 preload that adds the
  callable default interface expected by older lint plugins. It delegates every
  match to upstream minimatch 11.0.1 and preserves its named API. It preloads the
  facade before registering the resolution hook to avoid recursive loading.
- Adapt `makeRe(...).test(path)`, used by the import plugin's internal module
  restrictions, to the patched `Minimatch.match` method. The return is a matcher
  test object, not a RegExp; the facade supports the installed lint consumers
  rather than restoring removed regex generation or every historical v3 API.
- Keep the preload scoped to `npm run lint` and `npm run test:lint-deps`. The
  application build, server, component tests and other Node processes use normal
  module resolution. No installed dependency files are modified.
- Run compatibility regression tests in CI: CJS and ESM callers, ESLint's ESM
  configuration packages, React glob exceptions, side-effect import allowlists,
  accessibility controls, internal import allow/forbid patterns and the real
  Next React Hooks configuration. Each rule test checks that allowed code is
  accepted and a violation is still reported.

Use the repository's `npm run lint` command. Direct `npx eslint` does not load the
compatibility preload. Remove the preload and its script flags when ESLint and
its plugins support the patched matcher API without adaptation. Update the
version assertion in the compatibility test when updating the security pin.

## Validation and limits

The unadapted patched package reproduced real legacy plugin failures before the
facade was added. A clean `npm ci` must pass before publication, followed by all
frontend checks, the production routing fixture and both dependency audits.

Local backend tests run on Python 3.12 with SQLite. PostgreSQL migrations,
container checks and browser integration are verified by the existing remote CI
jobs on Python 3.13. No production deployments, configuration changes or database
writes are part of this repair.

Local validation on the final lockfiles: clean npm ci; nine lint dependency
regression checks; 137 component/unit tests; frontend lint, types, formatting and
production build; all five production routing checks; 695 backend tests; Ruff
lint/format and uv dependency consistency all pass. pip-audit reports no known
vulnerabilities and npm audit reports zero vulnerabilities. Fresh independent review found no remaining issues and separately ran all nine
lint dependency tests, frontend lint and whitespace checks. Remote CI status is
recorded on the PR before the repair is considered complete.
