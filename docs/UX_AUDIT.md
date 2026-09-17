# AegisGraph UX audit

Baseline captured on 2026-09-17 before this hardening pass changed application UI. The running production application at `127.0.0.1:3000` used synthetic Atlas data and the deterministic analyst. Twelve saved screenshots were individually opened and inspected at a 1600 × 1000 viewport. The in-app and connected Chrome tools were unavailable; the installed Playwright library controlled an isolated local Chrome session instead.

## Scope and decision

The interview task is to move from telemetry to an explainable incident, inspect evidence, question a bounded analyst, and explain the controls. The existing restrained dark interface is coherent. Preserve its navigation, tables, palette, and investigation workflow; improve the meaning and organization of the information rather than redesigning for novelty.

The twelve inspected baseline captures are published under `docs/screenshots/baseline/` so this audit remains reviewable from a clean checkout. Eight required portfolio captures and four supplementary captures are stored separately at the root of `docs/screenshots/` after verification.

## Numbered walkthrough

1. **Operations overview — healthy, targeted clarity opportunity.** Real counts, obvious incident entry, and simulated-data labeling establish a credible starting point. The connected-signals panel begins at 14:07 because it uses recent alerts; it should not be presented as the complete incident sequence. Keep this overview concise and put full chronology in the investigation. [Baseline](screenshots/baseline/01-overview.png)

2. **Security events — healthy.** Source/type filters, actor/IP/resource context, pagination, and expandable canonical records support the telemetry explanation. Preserve this working explorer; clearer event labels can improve both this route and the timeline without changing facts. [Baseline](screenshots/baseline/02-events.png)

3. **Detection rules — healthy.** Actual definitions distinguish single-event and temporal behavior, and show zero alerts for the untriggered rule. The visible descriptions are technically useful. Keep rules and triggered-alert counts distinct. [Baseline](screenshots/baseline/03-detections.png)

4. **Alerts — healthy.** Rule identity, descriptive conditions, severity, UTC time, and incident links are immediately visible. Preserve the table. Investigation timeline entries should expose these same detection names next to supporting evidence instead of requiring a separate tab. [Baseline](screenshots/baseline/04-alerts.png)

5. **Incident queue — healthy for one scenario.** One honest row is preferable to invented workload. The large empty area reflects the deliberately narrow dataset. A count of one is grammatically awkward but not a workflow blocker. Do not add decorative charts or fake cases to fill the page. [Baseline](screenshots/baseline/05-incidents.png)

6. **Incident workspace — highest priority.** Severity and source evidence are visible, but an edit form dominates the space before the investigation. There is no compact explanation of why ten alerts became one case. Two materially different events both read “Login”; “Mfa accept” and “Role assign” expose implementation vocabulary. Add factual server-derived correlation context, readable event interpretation, and linked detection context. Preserve baseline events as context rather than painting every event suspicious. [Baseline](screenshots/baseline/06-investigation.png)

7. **Evaluations — healthy evidence, weak scanability.** The page accurately shows 28 executed deterministic cases, and explicitly says no external model was called. Category coverage is hidden behind a select; case expectations and observations are not consistently separated. Add derived category summaries and clear expected/observed sections without manufacturing new results. Keep live-provider validation separate from deterministic results. [Baseline](screenshots/baseline/07-evaluations.png)

8. **Architecture — correct but too compressed.** The five-stage ingestion pipeline omits explicit alert/incident boundaries, while the analyst flow collapses schema and citation checks into “Validation.” Expand the technical sequence into two clearly labeled pipelines and mark the untrusted-telemetry, provider, and human-mutation boundaries. [Baseline](screenshots/baseline/08-architecture.png)

9. **Evidence drawer — healthy, improve source context.** The drawer clearly separates immutable source fields from analyst annotations and provides an explicit save. Source JSON is safely disclosed as text. Add useful normalized observation attributes and linked-detection context so trust/device, volume, and role facts do not require searching raw JSON. [Baseline](screenshots/baseline/09-evidence.png)

10. **Entity relationships — usable, details are too far below the graph.** The graph exposes linked identities and has a list alternative, but 36 entity chips push the selected entity's useful relationships, alerts, and evidence below the fold. Add type filtering/search and bring selected-entity context closer to selection. Preserve full labels and keyboard-accessible alternatives. [Baseline](screenshots/baseline/10-entities.png)

11. **Grounded answer — correct citations, weak answer hierarchy.** Valid citations open evidence, and provider identity is truthful. Summary and findings look like one continuous narrative, while the long form remains above the result. Add explicit Summary, Findings, Missing evidence, and Recommended next steps headings, show qualitative confidence and provider context clearly, and make the answer region navigable without hiding the source timeline. [Baseline](screenshots/baseline/11-grounded-answer.png)

12. **Insufficient evidence — functioning, improve intentionality.** The amber state is already distinct from a transport error, and no invented malware finding appears. Use the exact “What malware family was used?” example, emphasize the evidence limitation, and keep missing evidence and follow-up useful. [Baseline](screenshots/baseline/12-insufficient-evidence.png)

## Cross-cutting findings and acceptance checks

- There is no light theme or theme control. Add a functional persistent light/dark choice, preserving semantic severity and citation contrast in both themes. Verify it after navigation and reload.
- Repeated API-request evidence consumes most of the long timeline. Offer a clearly labeled grouped view that retains the exact event count and exposes every underlying evidence item. Never silently drop events or change their chronology.
- Preserve the UTC display, incident-bounded evidence, safe text rendering, keyboard tabs, modal focus behavior, explicit saves, and approval gates.
- Correlation must say principal plus event-time window and distinct-rule/family thresholds. Devices, sessions, and IPs supply context; they are not additional grouping predicates in this implementation.
- Empty, loading, insufficient-evidence, validation-rejected, and network-error states must remain distinguishable. Deterministic fixture results must not imply measured live-model reliability.

## Evidence limits

This baseline audit is a visual and interaction review, not a claim of WCAG compliance. Screenshots alone cannot establish screen-reader behavior, contrast ratios, focus order, data isolation, citation correctness, or prompt-injection resistance. Those require source review, targeted unit tests, browser checks in both themes and responsive sizes, and the independently executed backend/evaluation suite. Baseline analyst calls exercised only the configured deterministic provider; live-provider outcomes are documented separately under `docs/evaluations/`.

## Planned hardening

Implement compact actual correlation context; improve event/detection labeling and optional repetitive-event grouping; strengthen analyst answer structure; expose selected-entity evidence; clarify measured evaluation cases and architecture trust boundaries; add tested light mode. Keep the existing product scope and navigation. Final implementation and validation outcomes will be appended after those checks complete.

## Verified hardening outcomes

- The incident opens with its factual summary and server-derived correlation:
  one principal, ten alerts, nine rules, five families, and a 22-minute alert span
  against the actual 30-minute policy. Case editing is a disclosure below this context.
- The chronological timeline distinguishes familiar baseline activity from unfamiliar
  authentication, role changes, enumeration, resource access and privilege reversion.
  An optional API-burst group preserves all 18 underlying requests. Linked detection
  context, evidence citations, entity filters and normalized drawer fields are visible.
- Entity selection presents its source-event, alert and relationship counts above
  the graph. Search, type filters and keyboard-accessible entity buttons preserve
  an alternative to selecting graphical nodes.
- Analyst results separate summary, confidence, supported findings, missing evidence
  and next steps. Citation navigation worked with real OpenAI output. The malware
  question produced an intentional insufficient-evidence state with no findings.
- Evaluation categories and expected/observed results derive from executed records.
  The separate live view shows three latest passing cases, five local boundary checks,
  and all six provider attempts, including three earlier HTTP 429 failures.
- Architecture now separates the six-stage telemetry pipeline from the six-stage
  analyst pipeline and names the projection, provider, validation and human boundaries.
- Both themes persist across navigation and reload. A final mobile inspection caught
  and corrected a shadow from the closed navigation drawer. Its hidden navigation
  is also removed from keyboard interaction until opened.

All eight routes were checked in production against PostgreSQL. Browser tests cover
the complete deterministic investigation, seven dark-theme widths and three
light-theme widths. The final route trace had no page/console errors, HTTP failures
or unexpected request failures; navigation-canceled RSC prefetches are recorded
separately. See [validation](VALIDATION.md) and the [screenshot index](screenshots/README.md)
for executed totals and inspected captures. These checks do not establish WCAG
conformance or production readiness.
