"use client";
import Link from "next/link";
import { useCallback, useState } from "react";
import {
  ArrowLeft,
  Bell,
  Clock3,
  FileSearch,
  Network,
  Save,
} from "lucide-react";
import type { Entity, Incident, IncidentStatus, Severity } from "@/lib/types";
import { api, errorMessage } from "@/lib/api";
import { dateTime, humanize } from "@/lib/format";
import { Badge, ErrorNotice, Panel } from "./ui";
import { AlertTable } from "./data-tables";
import { EvidenceDrawer } from "./evidence-drawer";
import { EntityGraph } from "./entity-graph";
import { EvidenceAnalyst, type FindingDraft } from "./evidence-analyst";
import { Findings, NotesAndAudit, ReportPanel } from "./incident-records";
import { CorrelationSummary } from "./correlation-summary";
import { EvidenceTimeline } from "./evidence-timeline";
const tabs = [
  "Timeline",
  "Entities",
  "Alerts",
  "Findings",
  "Notes & audit",
  "Report",
] as const;
type Tab = (typeof tabs)[number];
const tabIds: Record<Tab, string> = {
  Timeline: "tab-timeline",
  Entities: "tab-entities",
  Alerts: "tab-alerts",
  Findings: "tab-findings",
  "Notes & audit": "tab-notes-audit",
  Report: "tab-report",
};
export function IncidentWorkspace({ initial }: { initial: Incident }) {
  const [incident, setIncident] = useState(initial);
  const [active, setActive] = useState<Tab>("Timeline");
  const [selectedEvidenceId, setSelectedEvidenceId] = useState<string | null>(
    null,
  );
  const [entityFilter, setEntityFilter] = useState<Entity | null>(null);
  const [draft, setDraft] = useState<FindingDraft | null>(null);
  const [draftKey, setDraftKey] = useState(0);
  const [status, setStatus] = useState<IncidentStatus>(initial.status);
  const [severity, setSeverity] = useState<Severity>(initial.severity);
  const [owner, setOwner] = useState(initial.owner || "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const endpoint = `/incidents/${encodeURIComponent(incident.id)}`;
  const refresh = useCallback(async () => {
    setIncident(
      await api<Incident>(`/incidents/${encodeURIComponent(initial.id)}`),
    );
  }, [initial.id]);
  const closeEvidence = useCallback(() => setSelectedEvidenceId(null), []);
  const openEvidence = useCallback((id: string) => {
    setSelectedEvidenceId(id);
  }, []);
  const selectedEvidence = incident.evidence.find(
    (item) => item.id === selectedEvidenceId,
  );
  async function saveIncident(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setSaved(false);
    try {
      await api(endpoint, {
        method: "PATCH",
        body: JSON.stringify({ status, severity, owner: owner.trim() || null }),
      });
      await refresh();
      setSaved(true);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }
  async function saveEvidence(id: string, relevance: string, note: string) {
    await api(`${endpoint}/evidence/${encodeURIComponent(id)}`, {
      method: "PATCH",
      body: JSON.stringify({ relevance, note }),
    });
    await refresh();
  }
  return (
    <>
      <Link className="back-link" href="/incidents">
        <ArrowLeft size={13} />
        Incident queue
      </Link>
      <div className="incident-heading">
        <div>
          <div className="inline-meta">
            <span className="mono">{incident.id}</span>
            <Badge value={incident.severity} />
            <Badge value={incident.status} />
          </div>
          <h1>{incident.title}</h1>
          <p>{incident.summary}</p>
          <div className="incident-strip">
            <span>
              <FileSearch size={13} />
              {incident.evidence.length} evidence items
            </span>
            <span>
              <Bell size={13} />
              {incident.alerts.length} linked alerts
            </span>
            <span>
              <Network size={13} />
              {incident.entities.length} entities
            </span>
            <span>
              <Clock3 size={13} />
              Opened {dateTime(incident.created_at)}
            </span>
            <span>Owner: {incident.owner || "Unassigned"}</span>
          </div>
        </div>
      </div>
      <CorrelationSummary correlation={incident.correlation} />
      <details className="incident-management">
        <summary>
          Manage incident{" "}
          <span>Update status, severity, or assigned analyst</span>
        </summary>
        <form className="panel incident-controls" onSubmit={saveIncident}>
          <div className="form-field">
            <label htmlFor="incident-status">Incident status</label>
            <select
              id="incident-status"
              value={status}
              onChange={(e) => {
                setStatus(e.target.value as IncidentStatus);
                setSaved(false);
              }}
            >
              {["new", "investigating", "contained", "resolved"].map((item) => (
                <option key={item} value={item}>
                  {humanize(item)}
                </option>
              ))}
            </select>
          </div>
          <div className="form-field">
            <label htmlFor="incident-severity">Severity</label>
            <select
              id="incident-severity"
              value={severity}
              onChange={(e) => {
                setSeverity(e.target.value as Severity);
                setSaved(false);
              }}
            >
              {["low", "medium", "high", "critical"].map((item) => (
                <option key={item} value={item}>
                  {humanize(item)}
                </option>
              ))}
            </select>
          </div>
          <div className="form-field">
            <label htmlFor="incident-owner">Assigned analyst</label>
            <input
              id="incident-owner"
              value={owner}
              maxLength={100}
              onChange={(e) => {
                setOwner(e.target.value);
                setSaved(false);
              }}
              placeholder="Unassigned"
            />
          </div>
          <button className="button secondary" type="submit" disabled={busy}>
            <Save size={14} />
            {busy ? "Saving…" : "Save changes"}
          </button>
          {error && (
            <div style={{ gridColumn: "1 / -1" }}>
              <ErrorNotice message={error} />
            </div>
          )}
          {saved && (
            <p
              role="status"
              style={{
                gridColumn: "1 / -1",
                fontSize: 12,
                color: "var(--teal)",
              }}
            >
              Incident changes saved and recorded in audit history.
            </p>
          )}
        </form>
      </details>
      <div className="investigation-grid">
        <Panel>
          <div className="tabs" role="tablist" aria-label="Investigation views">
            {tabs.map((tab) => (
              <button
                role="tab"
                key={tab}
                id={tabIds[tab]}
                aria-selected={active === tab}
                aria-controls="investigation-content"
                tabIndex={active === tab ? 0 : -1}
                onClick={() => setActive(tab)}
                onKeyDown={(e) => {
                  const index = tabs.indexOf(tab);
                  let next: number | undefined;
                  if (e.key === "ArrowRight") next = (index + 1) % tabs.length;
                  if (e.key === "ArrowLeft")
                    next = (index + tabs.length - 1) % tabs.length;
                  if (e.key === "Home") next = 0;
                  if (e.key === "End") next = tabs.length - 1;
                  if (next !== undefined) {
                    e.preventDefault();
                    setActive(tabs[next]);
                    document.getElementById(tabIds[tabs[next]])?.focus();
                  }
                }}
              >
                {tab}
                {tab === "Timeline" && (
                  <span className="tab-count">{incident.evidence.length}</span>
                )}
                {tab === "Findings" && incident.findings.length > 0 && (
                  <span className="tab-count">{incident.findings.length}</span>
                )}
              </button>
            ))}
          </div>
          <div
            id="investigation-content"
            role="tabpanel"
            aria-labelledby={tabIds[active]}
            tabIndex={0}
          >
            {active === "Timeline" && (
              <EvidenceTimeline
                incident={incident}
                entityFilter={entityFilter}
                onFilter={setEntityFilter}
                onEvidence={openEvidence}
              />
            )}
            {active === "Entities" && (
              <EntityGraph
                alerts={incident.alerts}
                entities={incident.entities}
                relationships={incident.relationships}
                evidence={incident.evidence}
                onEvidence={openEvidence}
                onFilter={(entity) => {
                  setEntityFilter(entity);
                  setActive("Timeline");
                }}
              />
            )}
            {active === "Alerts" && (
              <AlertTable items={incident.alerts} compact />
            )}
            {active === "Findings" && (
              <Findings
                key={draftKey}
                incident={incident}
                draft={draft}
                onEvidence={openEvidence}
                refresh={refresh}
              />
            )}
            {active === "Notes & audit" && (
              <NotesAndAudit incident={incident} refresh={refresh} />
            )}
            {active === "Report" && (
              <ReportPanel
                key={incident.updated_at}
                incidentId={incident.id}
                refresh={refresh}
                evidence={incident.evidence}
                onEvidence={openEvidence}
              />
            )}
          </div>
        </Panel>
        <EvidenceAnalyst
          incidentId={incident.id}
          evidenceCount={incident.evidence.length}
          onEvidence={openEvidence}
          onComplete={refresh}
          onDraft={(value) => {
            setDraft(value);
            setDraftKey((key) => key + 1);
            setActive("Findings");
          }}
        />
      </div>
      {selectedEvidence && (
        <EvidenceDrawer
          key={selectedEvidence.id}
          evidence={selectedEvidence}
          alerts={incident.alerts.filter((alert) =>
            alert.event_ids.includes(selectedEvidence.event_id),
          )}
          onClose={closeEvidence}
          onSave={saveEvidence}
        />
      )}
    </>
  );
}
