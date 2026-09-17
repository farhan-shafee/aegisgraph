# AegisGraph: 5–7 minute interview walkthrough

Run migrations, seed the synthetic environment, and start both servers using the
README. Set `AI_PROVIDER=deterministic` in the API terminal for a reproducible
demonstration. Open [the local application](http://127.0.0.1:3000). Reset only the disposable demo database before the session
if you want to start with unreviewed findings and an untouched audit history.

## 0:00–0:40 — Frame the system

“AegisGraph is an evidence-grounded investigation platform for a fictional Atlas
Trading Platform. Every identity, financial resource and event here is synthetic.
It takes events through normalization, detection, correlation and investigation.
AI assists only after the evidence set exists.”

Open operations. A fresh default seed contains 4,026 events, 10 alerts, and one
incident. Point out that displayed counts come from persisted records. There is no
claim of operational coverage, reduced response time, or real customer adoption.

## 0:40–1:30 — Telemetry and detection

Open Events and filter a source. Show a normal observation and its actor, device,
session and target. Explain that four adapters produce the same canonical model.
Open Detections and inspect a rule's conditions/window.

“A login from a new device is a signal, not proof of compromise. The thresholds
are explicit and testable. Detection creates an alert; correlation is a different
step that combines related alerts and context.”

“The actual correlation rule requires one principal, at least three distinct
rules across two families, and at most 30 minutes from the first alert. Session,
device, and IP relationships help investigation; they are not additional case
grouping predicates.”

## 1:30–2:40 — The incident and timeline

Open the high-severity engineer-account incident. Read the correlation rationale.
Walk the chronological sequence: recognized login at 13:57, new source/device at
14:02, MFA acceptance at 14:03, role assignment at 14:07, enumeration at 14:11,
sensitive resource access at 14:14, high volume at 14:17, another device/session
at 14:21, role reversion at 14:24. The timestamps belong to the synthetic dataset,
not a live operational feed.

Click an evidence entry to inspect the exact source. Mark one observation relevant
and save a note. Explain that the annotation changes case interpretation while
the canonical event remains intact.

“Migrations install event and audit triggers that reject ordinary updates and
deletes. The database owner can remove those protections; this is not tamper-proof
evidence storage.”

## 2:40–3:20 — Relationships

Open the entity view. Select the engineer, an unusual device, and its session.
Show related evidence and relationships. Mention the accessible list alternative.

“The graph is derived from relational evidence associations. These links show
co-occurrence and identity relationships, not confirmed attacker identity. V1
doesn't need a graph database for this bounded traversal.”

## 3:20–4:25 — Evidence Analyst

Ask: **What most likely happened?**

Read a supported observation and click its evidence citation. Call out the analyst
mode displayed by the interface.

“This reproducible run uses the deterministic provider. An optional external model
uses the same interface and validation. The provider proposes structured claim
types. The server verifies context membership and event predicates, then renders
the factual statement. An existing citation alone does not make arbitrary prose
true.”

“The API retrieves at most 50 case evidence rows for analysis. Rows marked benign
are excluded and the answer discloses that count. The account-misuse interpretation
is labeled as a hypothesis, not a confirmed attribution or calibrated probability.”

Ask: **What malware family was used?**

Show the insufficient-evidence response. Optionally ask: **Why did the attacker
exfiltrate SSNs?**

“The observations support suspicious access and privilege activity. They don't
establish malware execution, SSN exfiltration, a real person's identity, or the
attacker's country.”

## 4:25–5:10 — Executed evaluations

Open Evaluations and run the suite. Show actual case counts and individual details:
invalid citation, cross-case reference, malformed output, false premise, and
prompt-injection text in telemetry.

“These are deterministic boundary tests executed now. They are not a percentage
claim about arbitrary model behavior. Live-model adversarial testing is a separate
measurement, and no live-model score is invented.”

## 5:10–6:10 — Human workflow and architecture

Save a finding with selected evidence and approve it explicitly. Generate the
report, review the draft, and approve through the human action. Inspect the audit
history to distinguish analyst actions from system/model events.

“This report is a deterministic template containing source evidence and approved
findings; the model did not write it. A later case annotation or finding change
marks it stale, clears approval, and requires regeneration and review.”

If time permits, add a note after approval and return to Report to show the stale
state and corresponding audit entry. Regenerate before approving it again.

Open Architecture. Trace normalized observations → alerts → incident scope →
bounded provider context → validators → analyst review.

“The provider has no incident write functions, database handle, command tool or
authorization authority. Production still needs real identity, case entitlements,
tenant isolation, external audit retention, and operational hardening.”

## 6:10–6:40 — Close

“The engineering focus is reproducible correlation, inspectable evidence, and a
narrow AI boundary. It is a working local investigation system with documented
limits. Production identity, authorization, and operational scale remain future
engineering work.”

## If something fails during a demo

Use the visible error and request ID. Check `/health`, database connectivity and
server logs. Do not imply a recorded screenshot is live data. If the external
provider is unavailable, restart with `AI_PROVIDER=deterministic` and identify the
mode clearly. No external API key is required for the normal walkthrough.
