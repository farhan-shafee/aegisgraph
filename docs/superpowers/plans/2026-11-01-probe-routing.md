# Probe Routing Implementation Plan

> Execute inline using superpowers:executing-plans and test-driven-development.

**Goal:** Stop nonexistent-page probes consuming runtime-check capacity.
**Architecture:** A layout-free catch-all 404; unchanged validation on real routes.
**Tech Stack:** Existing Next.js 16, TypeScript, Vitest, Node HTTPS fixtures.
**Spec:** ../specs/2026-11-01-probe-routing-design.md

## Global Constraints

- Preserve public-demo runtime validation, origin checks, API budgets and local mode.
- No live traffic burst, credentials, database operations or API deployment.
- Never treat DNS proxying as protection against direct-origin access.

## Review Focus

- Catch-all must not shadow existing page, dynamic page, static asset or API routes.
- Unknown paths must remain 404 with no upstream access when runtime is throttled.
- Unsafe runtime contracts must still deny application content.
- Retry guidance must be numeric and bounded; private upstream detail stays hidden.
- Malformed API paths must be rejected without upstream access.

## Task 1: Reproduce and repair routing

- [x] Add a database-free production-server regression harness with local HTTPS.
- [x] Run it against the original build and observe unwanted runtime requests.
- [x] Add the catch-all route and reject malformed API segments first.
- [x] Preserve safe retry guidance on runtime-unavailable API responses.
- [x] Run focused unit tests, full frontend suite, lint, types and production build.
- [x] Run the production regression harness with safe, throttled and unsafe runtimes.
- [ ] Review the diff and publish a reviewable branch/PR with exact validation.
- [ ] Verify production rollout prerequisites and report any remaining boundary.
