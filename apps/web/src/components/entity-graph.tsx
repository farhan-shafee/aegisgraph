"use client";
import { useState } from "react";
import { ArrowRight, Filter, Network } from "lucide-react";
import type { Alert, Entity, Evidence, Relationship } from "@/lib/types";
import { evidenceForEntity, humanize } from "@/lib/format";
import { Badge, Empty } from "./ui";
export function EntityGraph({
  entities,
  relationships,
  evidence,
  alerts,
  onEvidence,
  onFilter,
}: {
  entities: Entity[];
  relationships: Relationship[];
  evidence: Evidence[];
  alerts: Alert[];
  onEvidence: (id: string) => void;
  onFilter: (entity: Entity) => void;
}) {
  const [selectedId, setSelectedId] = useState(
    entities.find((e) => e.type === "user")?.id || entities[0]?.id,
  );
  const selected = entities.find((e) => e.id === selectedId);
  if (!selected) return <Empty title="No linked entities" />;
  const links = relationships.filter(
    (r) => r.source === selected.id || r.target === selected.id,
  );
  const neighbors = new Set(links.flatMap((r) => [r.source, r.target]));
  neighbors.delete(selected.id);
  const graphEntities = [
    selected,
    ...entities.filter((e) => neighbors.has(e.id)).slice(0, 10),
  ];
  const positions = graphEntities.map((entity, index) =>
    index === 0
      ? { entity, x: 390, y: 205 }
      : {
          entity,
          x:
            390 +
            Math.cos(
              ((index - 1) / Math.max(graphEntities.length - 1, 1)) *
                Math.PI *
                2 -
                Math.PI / 2,
            ) *
              280,
          y:
            205 +
            Math.sin(
              ((index - 1) / Math.max(graphEntities.length - 1, 1)) *
                Math.PI *
                2 -
                Math.PI / 2,
            ) *
              150,
        },
  );
  const related = evidenceForEntity(selected, evidence, relationships);
  const relatedEventIds = new Set(related.map((item) => item.event_id));
  const relatedAlerts = alerts.filter((alert) =>
    alert.event_ids.some((id) => relatedEventIds.has(id)),
  );
  const labelFor = (id: string) =>
    entities.find((e) => e.id === id)?.label || id;
  return (
    <>
      <p className="graph-explanation">
        Select an entity to inspect its evidence and relationships. The graph
        shows up to ten neighbors; the entity list includes every linked entity.
      </p>
      <div className="graph-wrap">
        <svg
          className="entity-graph"
          viewBox="0 0 780 430"
          role="img"
          aria-label={`Relationships for ${selected.label}; the interactive entity list follows.`}
        >
          {positions.slice(1).map((p) => (
            <line
              className="graph-edge"
              key={p.entity.id}
              x1={390}
              y1={205}
              x2={p.x}
              y2={p.y}
            />
          ))}
          {positions.map(({ entity, x, y }, i) => (
            <g
              key={entity.id}
              className={`graph-node ${i === 0 ? "primary selected" : ""}`}
              role="button"
              tabIndex={0}
              aria-label={`Select ${humanize(entity.type)} ${entity.label}`}
              onClick={() => setSelectedId(entity.id)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  setSelectedId(entity.id);
                }
              }}
            >
              <circle cx={x} cy={y} r={i === 0 ? 25 : 18} />
              <text x={x} y={y + 4} style={{ fontSize: 12 }}>
                {entity.type.slice(0, 1).toUpperCase()}
              </text>
              <text x={x} y={y + (i === 0 ? 43 : 35)}>
                {entity.label.length > 26
                  ? `${entity.label.slice(0, 24)}…`
                  : entity.label}
              </text>
              <text className="graph-type" x={x} y={y + (i === 0 ? 57 : 49)}>
                {entity.type}
              </text>
            </g>
          ))}
        </svg>
      </div>
      <div className="entity-list" aria-label="Incident entities">
        {entities.map((entity) => (
          <button
            key={entity.id}
            aria-pressed={selected.id === entity.id}
            onClick={() => setSelectedId(entity.id)}
          >
            {humanize(entity.type)} · {entity.label}
          </button>
        ))}
      </div>
      <section className="entity-detail" aria-label="Selected entity">
        <div className="inline-meta">
          <Network size={16} />
          <h3>{selected.label}</h3>
          <span className="source-chip">{selected.type}</span>
        </div>
        <p className="page-note">
          {related.length} evidence items · {links.length} relationships
        </p>
        <ul className="relationship-list">
          {links.map((link, i) => (
            <li key={`${link.source}-${link.target}-${i}`}>
              <span>{labelFor(link.source)}</span>
              <ArrowRight size={12} />
              <span className="relationship-label">{link.label}</span>
              <span>{labelFor(link.target)}</span>
            </li>
          ))}
        </ul>
        <div className="citation-group">
          {related.map((item) => (
            <button
              className="evidence-citation"
              key={item.id}
              onClick={() => onEvidence(item.id)}
            >
              {item.id}
            </button>
          ))}
        </div>
        <h3 style={{ marginTop: 18 }}>
          Related alerts ({relatedAlerts.length})
        </h3>
        <ul className="relationship-list">
          {relatedAlerts.map((alert) => (
            <li key={alert.id}>
              <Badge value={alert.severity} />
              <span>{alert.title || alert.rule_name}</span>
            </li>
          ))}
        </ul>
        <button
          className="button secondary small"
          style={{ marginTop: 16 }}
          onClick={() => onFilter(selected)}
        >
          <Filter size={13} />
          Filter timeline to this entity
        </button>
      </section>
    </>
  );
}
