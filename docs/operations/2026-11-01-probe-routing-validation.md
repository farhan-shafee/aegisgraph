# November 1 probe routing repair

## Evidence and scope

The 12:20 p.m. EST incident included 35 frontend HTTP 500s and 35 API
`/api/runtime` HTTP 429s. The deployed root layout checked the public runtime even
for missing pages. Production remained healthy after the burst.

The patch adds a layout-free catch-all 404 handler and rejects malformed API paths
before backend access. It carries validated numeric retry guidance through runtime
unavailability to the API proxy's existing 503 response. Runtime validation,
deterministic/public read-only requirements, API budgets and database code remain
unchanged.

## Local verification

- Before the patch, the database-free production-server regression observed 12
  runtime calls for 12 nonexistent-page/malformed-path GET/HEAD requests.
- The added unit regressions failed before implementation: retry guidance was
  absent, and malformed paths returned 503 when the runtime check failed.
- After the patch, all 137 frontend tests passed. Production build, types, lint,
  formatting and diff whitespace checks passed.
- The production-server regression passed five checks: missing-path independence;
  real-page validation; specific dynamic/API/static route precedence; missing-path
  404s during throttling with safe API retry guidance; and denial of application
  data access when the public runtime contract is unsafe.
- The harness uses only loopback servers, an ephemeral locally trusted HTTPS
  certificate and synthetic fixtures. It performs no database or live load test.
- A fresh independent reviewer found no Critical or Important issues and reran
  all five production-server regression checks successfully. One nonblocking test
  coverage note remains: the integration harness does not separately assert the
  404 response's Cache-Control header or empty HEAD body; both are implemented.

## Separate dependency-audit finding

The existing locked toolchain's `npm audit --audit-level=moderate` exits 1 with
16 moderate transitive findings rooted in minimatch, GHSA-g3hv-75wg-m249.
The routing patch does not change package.json or package-lock.json. The installed
affected paths are ESLint/ESLint plugins (minimatch 3.1.5) and TypeScript ESLint
(minimatch 10.2.6). The published advisory lists 11.0.1 as patched. npm proposes
an incompatible forced ESLint downgrade; that was not applied. The full required
frontend CI gate therefore cannot be called green, despite the passing build,
tests, types, lint and formatting checks. Treat this as a separate dependency
remediation or explicit release-risk decision, not as a routing-test failure.

Primary advisory: https://github.com/advisories/GHSA-g3hv-75wg-m249

## Publication status

Implementation commit `2c56b3a180b003a79d76c6d4af88e4a65456d531` is local.
Automatic approval review rejected the attempted GitHub branch push because
explicit publishing authorization was missing and repository contents might be
disclosed. A read-only remote-ref check confirmed no matching published branch.
No alternative publication mechanism was attempted; no PR, deployment or DNS/WAF
change was made. Production remains on its previous deployment.

## Release and remaining limitations

This document records local verification, not a production deployment receipt.
The planned web-only release must identify its exact commit and deployment before
the incident is called fixed in production. No API deployment or migration is
required. Retain web deployment `b1ace76a-c522-4198-abda-d031a0a7d7b9` as the rollback
reference; its source is `8c24a1287c6581e95ba5912b7d68371cc597ae6d`.

Cloudflare DNS proxying and direct-origin protection are not changed. Genuine
application routes still share the original API budget; an unavailable runtime
continues to fail closed on those pages. The repair removes the observed
nonexistent-page amplification without weakening those boundaries.
