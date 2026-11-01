# Probe routing and throttling repair

The November 1 probe burst made nonexistent pages execute the root layout's
`/api/runtime` check. The shared API read budget returned 35 HTTP 429s, which
became 35 page-rendering HTTP 500s. The custom hostname is Cloudflare DNS only.

## Approach

Use a root catch-all **route handler** for unmatched page paths. It returns a
small, uncached 404 without rendering a layout or calling the API. Specific page
and API routes retain priority. This avoids duplicating the site's route list or
introducing a trusted request-header contract. Moving every page into a route
group would cause broader churn; increasing or removing the API budget would
leave the amplification intact.

Validate malformed API path segments before checking the backend. Preserve safe
numeric Retry-After guidance when runtime throttling makes the API proxy return
503. Keep real-page runtime validation, public read-only/deterministic checks,
origin validation, and the API budgets intact.

## Verification and release boundary

Use a local HTTPS fixture and a production Next build to verify unknown paths
make zero backend calls even while the backend returns 429, specific routes
remain usable, and unsafe public runtime contracts still fail closed. No live
load test, database access, reseeding, or API deployment is needed.

Cloudflare proxy/WAF changes need separate verification of origin access and
rollback. Changing DNS alone does not prevent access to the Railway origin.
Prepare and validate the code before any production rollout.
