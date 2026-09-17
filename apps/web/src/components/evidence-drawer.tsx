"use client";
import { useEffect, useRef, useState } from "react";
import { Check, FileJson, X } from "lucide-react";
import type { Evidence } from "@/lib/types";
import { dateTime, eventLabel, humanize } from "@/lib/format";
import { errorMessage } from "@/lib/api";
import { Badge, ErrorNotice } from "./ui";
export function EvidenceDrawer({
  evidence,
  onClose,
  onSave,
}: {
  evidence: Evidence;
  onClose: () => void;
  onSave: (id: string, relevance: string, note: string) => Promise<void>;
}) {
  const [relevance, setRelevance] = useState(evidence.relevance),
    [note, setNote] = useState(evidence.note || ""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState<string | null>(null),
    [saved, setSaved] = useState(false);
  const dialog = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null,
      root = dialog.current;
    root?.querySelector<HTMLButtonElement>("button")?.focus();
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    function keydown(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
      if (event.key !== "Tab" || !root) return;
      const items = Array.from(
        root.querySelectorAll<HTMLElement>(
          'button:not([disabled]), a[href], input, select, textarea, summary, [tabindex="0"]',
        ),
      );
      const first = items[0],
        last = items.at(-1);
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last?.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first?.focus();
      }
    }
    document.addEventListener("keydown", keydown);
    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener("keydown", keydown);
      previous?.focus();
    };
  }, [onClose]);
  const event = evidence.event;
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setSaved(false);
    try {
      await onSave(evidence.id, relevance, note);
      setSaved(true);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }
  const fields = [
    ["Source", humanize(event.source)],
    ["Event ID", event.event_id],
    ["Event type", humanize(event.event_type)],
    ["Outcome", humanize(event.outcome)],
    ["Identity", event.actor?.username || event.actor?.user_id],
    ["Role", event.actor?.role],
    ["Source IP", event.network?.source_ip],
    ["Device", event.device?.device_id],
    [
      "Device trust",
      event.device?.trusted === undefined
        ? undefined
        : event.device.trusted
          ? "Recognized"
          : "Unrecognized",
    ],
    ["Session", event.session?.session_id],
    ["Service", event.target?.service],
    [
      "Endpoint / resource",
      event.target?.endpoint || event.target?.resource_id,
    ],
  ];
  return (
    <div
      className="drawer-backdrop"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        className="evidence-drawer"
        role="dialog"
        aria-modal="true"
        aria-labelledby="evidence-title"
        ref={dialog}
      >
        <div className="drawer-top">
          <div className="eyebrow" style={{ margin: 0 }}>
            SOURCE EVIDENCE
          </div>
          <button
            className="icon-button"
            onClick={onClose}
            aria-label="Close evidence"
          >
            <X size={18} />
          </button>
        </div>
        <div className="inline-meta">
          <span className="evidence-citation">{evidence.id}</span>
          <Badge value={evidence.relevance} />
        </div>
        <h2 id="evidence-title">{eventLabel(event)}</h2>
        <p className="summary-time">{dateTime(event.timestamp)}</p>
        <dl className="detail-grid">
          {fields.map(([label, value]) => (
            <div key={label}>
              <dt>{label}</dt>
              <dd>{value || "Not recorded"}</dd>
            </div>
          ))}
        </dl>
        <form className="evidence-editor" onSubmit={submit}>
          <h3>Analyst assessment</h3>
          <p className="page-note" style={{ margin: 0 }}>
            Annotations update this case. The source event remains immutable.
          </p>
          <div className="form-field">
            <label htmlFor="evidence-relevance">Relevance</label>
            <select
              id="evidence-relevance"
              value={relevance}
              onChange={(e) => {
                setRelevance(e.target.value);
                setSaved(false);
              }}
            >
              <option value="unreviewed">Unreviewed</option>
              <option value="relevant">Relevant</option>
              <option value="benign">Benign</option>
            </select>
          </div>
          <div className="form-field">
            <label htmlFor="evidence-note">Evidence annotation</label>
            <textarea
              id="evidence-note"
              value={note}
              maxLength={2000}
              onChange={(e) => {
                setNote(e.target.value);
                setSaved(false);
              }}
              placeholder="Record context, alternative explanations, or your assessment…"
            />
          </div>
          <ErrorNotice message={error} />
          <button className="button primary" disabled={busy} type="submit">
            {busy ? "Saving…" : "Save assessment"}
          </button>
          {saved && (
            <p className="notice success" role="status">
              <Check size={15} />
              Evidence assessment saved.
            </p>
          )}
        </form>
        <details className="source-details">
          <summary>
            <FileJson size={14} style={{ display: "inline", marginRight: 6 }} />
            Inspect canonical source event
          </summary>
          <pre>{JSON.stringify(event, null, 2)}</pre>
        </details>
      </div>
    </div>
  );
}
