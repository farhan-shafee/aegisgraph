# AegisGraph: seven-minute interview walkthrough

The aim is to show an investigation, then explain the engineering decisions that
make its evidence and AI boundaries inspectable. All observations are synthetic.
Keep the [interview notes](INTERVIEW_NOTES.md) available for follow-up questions.

## Prepare once

Install dependencies using the [README](../README.md). Stop an existing demo API
before resetting its data. From the repository root, with the virtual environment
active:

```sh
python -m aegisgraph.cli demo-reset
python -m aegisgraph.cli demo-api
```

In a second terminal:

```sh
npm run dev --prefix apps/web
```

In a third terminal, with the virtual environment active:

```sh
python -m aegisgraph.cli demo-health
```

Reset is destructive **only to the reserved disposable demo database**. It applies
migrations, regenerates deterministic telemetry, detections and correlation, and
runs deterministic evaluations. It ignores an arbitrary `DATABASE_URL`. The default
is the reserved SQLite demo file. The reset/API commands also support
`--postgres-port 55432` for a pre-created local PostgreSQL `aegisgraph_demo` database;
use the same selection for both commands. This does not target the original
`aegisgraph` database or an arbitrary database name.

The default demo API explicitly uses the deterministic provider even when `.env`
selects OpenAI. For a live session, start `demo-api --provider openai` instead.
This reads the existing server-only configuration and may incur API charges.
Run the explicit live evaluation command documented in
[evaluations](evaluations/README.md) before relying on external availability.
Never show `.env`, authorization headers, or terminal environment dumps on screen.

Open [AegisGraph](http://127.0.0.1:3000), choose the intended theme, and confirm
4,026 events, ten alerts, and one incident. Use a fresh reset for a clean approval
and annotation history. Dates in the case belong to the synthetic dataset;
they are not a live feed.

## 00:00–00:30 — Explain the product

Open Operations.

> AegisGraph is an evidence-grounded investigation application for a simulated
> fintech environment. It takes telemetry through normalization, detection,
> correlation, evidence review, and a bounded AI analyst. The evidence scope
> exists before the model runs.

Point out persisted counts and the primary incident. Do not claim customer usage,
measured response-time reduction, or production detection coverage.

## 00:30–01:15 — Inspect telemetry and the canonical model

Open Security events, filter a source, and inspect a normal observation. Show
timestamp, actor, device, session, target, and source reference.

> Four adapters normalize identity, gateway, endpoint, and Atlas application
> observations. The source record stays unchanged; a relevance decision is a
> separate case annotation. A well-formed event is not necessarily true.

Explain the 4,000 baseline observations and 26 scenario observations. Not every
event is suspicious; baseline context makes later activity interpretable.

## 01:15–02:00 — Connect detection-as-code to alerts

Open Detections, inspect the endpoint enumeration rule, then open Alerts.

> The rule requires twelve distinct internal endpoints within five minutes for
> one user/session. A detection emits an alert with source evidence. Ten rules
> are defined; nine distinct rules fire in this case and produce ten alerts.

Show a weak authentication signal next to a stronger privilege/access signal.
Thresholds are explicit synthetic policy, not calibrated detection performance.

## 02:00–02:45 — Explain why one incident exists

Open the primary incident and its correlation explanation.

> These alerts share one principal over 22 minutes. The grouping policy requires
> at least three distinct rules across two families within 30 minutes anchored
> at the first alert. This case has nine rules across five families. Shared
> device, session, and IP relationships help investigate; they do not independently
> decide which alerts enter the case.

Point out severity, status, owner, event-time range, and the summary. High severity
is an explicit policy based on the rule mix, not a learned compromise probability.

## 02:45–03:45 — Follow the chronology and evidence

Walk the sequence in UTC:

1. 13:57 — familiar baseline authentication.
2. 14:02 — unfamiliar source/device.
3. 14:03 — MFA accepted.
4. 14:07 — privileged role assigned.
5. 14:11 — repeated internal endpoint requests.
6. 14:14 — sensitive account resource accessed.
7. 14:17 — elevated record volume.
8. 14:21 — another unfamiliar device/session.
9. 14:24 — privileged role reverted.

Open source evidence. Show its ID, normalized fields, source reference, and
separate annotation. Open Entities and select the principal or unusual device;
follow a linked observation back to evidence.

> Relationships explain which observations connect. They do not prove who
> operated the account. Database triggers reject ordinary event edits/deletes;
> a privileged owner can remove those protections.

## 03:45–04:45 — Ask the Evidence Analyst

Ask exactly: **What most likely happened?**

Read the summary, one structured finding, and the missing evidence. Click a
citation and verify that it opens the corresponding observation. Name the visible
provider: deterministic or OpenAI. Never imply a deterministic answer came from
an external model.

> The provider chooses typed observations and exact supporting evidence sets.
> The server checks schema, current-case scope, inclusion in the actual bounded
> context, and claim support before rendering factual statements. A real citation
> alone would not justify arbitrary prose. The confidence label is qualitative,
> not a calibrated probability. Account misuse remains a hypothesis.

If useful, select Review as finding to demonstrate that saving and approving
require explicit human actions. The model cannot perform those actions.

## 04:45–05:20 — Show intentional insufficient evidence

Ask exactly: **What malware family was used?**

Show the insufficient-evidence outcome and missing endpoint evidence.

> Suspicious identity and access activity does not establish malware execution
> or a malware family. This is a successful evidence-boundary outcome, not an
> application error. High access volume also does not prove exfiltration.

## 05:20–06:00 — Inspect executed evaluations

Open Evaluations. Show deterministic case totals, one prompt-injection case,
and its expected versus actual behavior. Inspect the separate live-provider record
and its actual attempts/outcomes, if present.

> Deterministic fixtures test application enforcement. The malicious telemetry
> fixture is filtered by the context projection before it reaches a provider.
> That does not measure a model resisting text it never saw. Live calls are
> reported separately, including failures; a small successful sample is not a
> universal prompt-injection resistance score.

Running the ordinary evaluation suite never initiates paid external calls.

## 06:00–07:00 — Finish at the trust boundaries

Open Architecture. Trace telemetry → normalization → detection → alerts →
correlation → incident → bounded retrieval → provider → schema/citation/support
validation → human review.

> The database is the system of record. Telemetry is untrusted, scope is
> deterministic, and citations are validated outside the model. The provider
> has no database handle, retrieval tool, or incident mutation authority.

Explain that reports are deterministic templates with explicit approval; later
case changes mark them stale and require regeneration. The current report and
audit actions are stored, not immutable historical report versions.

> Production would require authenticated identities and case entitlements,
> tenant isolation, independently retained evidence/audits, authenticated
> ingestion, and measured operational scaling. This release demonstrates the
> investigation and evidence boundary, with those limits stated explicitly.

## If a dependency fails during the interview

Run `demo-health` and use visible request IDs to diagnose local failures.
Provider-unavailable is different from insufficient evidence. An HTTP/provider
failure is not a successful live test. Restart the API without `--provider openai`
for an explicitly labeled deterministic walkthrough; do not silently impersonate
a working live provider. Recorded screenshots are useful portfolio artifacts,
not a substitute for claiming an unavailable screen is live.
