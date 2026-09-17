"use client";
import { useState } from "react";
import { ArrowUpRight, FilterX, Layers3 } from "lucide-react";
import type { Entity, Evidence, Incident } from "@/lib/types";
import {
  eventContext,
  eventLabel,
  evidenceForEntity,
  humanize,
  time,
} from "@/lib/format";
import { groupTimeline } from "@/lib/timeline";
import { Badge, Empty } from "./ui";
export function EvidenceTimeline({
  incident,
  entityFilter,
  onFilter,
  onEvidence,
}: {
  incident: Incident;
  entityFilter: Entity | null;
  onFilter: (entity: Entity | null) => void;
  onEvidence: (id: string) => void;
}) {
  const [compact, setCompact] = useState(true);
  const evidence = entityFilter
    ? evidenceForEntity(entityFilter, incident.evidence, incident.relationships)
    : incident.evidence;
  const groups = groupTimeline(evidence, compact);
  function card(item: Evidence) {
    const entityIds = new Set(
      incident.relationships
        .filter((r) => r.evidence_ids.includes(item.id))
        .flatMap((r) => [r.source, r.target]),
    );
    const entities = incident.entities
      .filter((entity) => entityIds.has(entity.id))
      .sort(
        (a, b) =>
          Number(b.type === "device" || b.type === "session") -
          Number(a.type === "device" || a.type === "session"),
      )
      .slice(0, 3);
    const alerts = incident.alerts.filter((alert) =>
      alert.event_ids.includes(item.event_id),
    );
    return (
      <div className="timeline-card">
        <button className="timeline-title" onClick={() => onEvidence(item.id)}>
          {eventLabel(item.event)}
          <ArrowUpRight size={14} />
        </button>
        <p className="timeline-context">{eventContext(item.event)}</p>
        {alerts.length > 0 && (
          <div className="timeline-detections" aria-label="Linked detections">
            {alerts.map((alert) => (
              <span key={alert.id}>
                <span className={`signal-dot ${alert.severity}`} />
                {alert.rule_id} · {alert.rule_name}
              </span>
            ))}
          </div>
        )}
        <div className="timeline-tags">
          <button
            className="evidence-citation"
            onClick={() => onEvidence(item.id)}
            aria-label={`Inspect evidence ${item.id}`}
          >
            {item.id}
          </button>
          {entities.map((entity) => (
            <button
              className="entity-tag"
              key={entity.id}
              onClick={() => onFilter(entity)}
              aria-label={`Filter timeline by ${entity.label}`}
            >
              {entity.label}
            </button>
          ))}
        </div>
        {item.note && <p className="timeline-note">{item.note}</p>}
      </div>
    );
  }
  return (
    <>
      <div className="timeline-heading">
        <div>
          <h2>Evidence timeline</h2>
          <p>{evidence.length} source events · chronological · UTC</p>
        </div>
        <label className="compact-toggle">
          <input
            type="checkbox"
            checked={compact}
            onChange={(e) => setCompact(e.target.checked)}
          />
          Group API bursts
        </label>
      </div>
      {entityFilter && (
        <div className="timeline-filter">
          <span>Showing evidence related to {entityFilter.label}</span>
          <button className="button ghost small" onClick={() => onFilter(null)}>
            <FilterX size={12} />
            Clear entity filter
          </button>
        </div>
      )}
      {groups.length ? (
        <ol className="timeline-list">
          {groups.map((group) => {
            const first = group.items[0];
            return (
              <li className={`timeline-item ${first.relevance}`} key={group.id}>
                <span className="timeline-marker" />
                <div className="timeline-meta">
                  <time dateTime={first.timestamp}>
                    {time(first.timestamp)}
                  </time>
                  <span className="source-chip">
                    {humanize(first.event.source)}
                  </span>
                  {group.items.length === 1 &&
                    first.relevance !== "unreviewed" && (
                      <Badge value={first.relevance} />
                    )}
                </div>
                {group.items.length === 1 ? (
                  card(first)
                ) : (
                  <details className="timeline-burst">
                    <summary>
                      <Layers3 size={16} />
                      <span>
                        <strong>
                          {group.items.length} API requests across{" "}
                          {
                            new Set(
                              group.items
                                .map((item) => item.event.target?.endpoint)
                                .filter(Boolean),
                            ).size
                          }{" "}
                          endpoints
                        </strong>
                        <small>
                          {time(first.timestamp)}–
                          {time(group.items.at(-1)!.timestamp)} UTC · same
                          principal and session
                        </small>
                        <small className="burst-detection">
                          {incident.alerts
                            .filter((alert) =>
                              group.items.some((item) =>
                                alert.event_ids.includes(item.event_id),
                              ),
                            )
                            .map(
                              (alert) =>
                                `${alert.rule_id} · ${alert.rule_name}`,
                            )
                            .join("; ")}
                        </small>
                      </span>
                      <span className="burst-expand">Inspect all events</span>
                    </summary>
                    <p className="burst-context">
                      {incident.alerts
                        .filter((alert) =>
                          group.items.some((item) =>
                            alert.event_ids.includes(item.event_id),
                          ),
                        )
                        .map((alert) => `${alert.rule_id} · ${alert.rule_name}`)
                        .join("; ") ||
                        "Source events grouped for readability. No detection conclusion is inferred."}
                    </p>
                    <ol className="burst-events">
                      {group.items.map((item) => (
                        <li key={item.id}>
                          <div className="timeline-meta">
                            <time>{time(item.timestamp)}</time>
                            <Badge value={item.relevance} />
                          </div>
                          {card(item)}
                        </li>
                      ))}
                    </ol>
                  </details>
                )}
              </li>
            );
          })}
        </ol>
      ) : (
        <Empty title="No evidence matches this entity" />
      )}
    </>
  );
}
