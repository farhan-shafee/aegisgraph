import type { Evidence, Entity, Relationship, SecurityEvent } from "./types";
export function humanize(value: string): string {
  return value.replace(/[_-]/g, " ").replace(/^./, (s) => s.toUpperCase());
}
export function time(value: string): string {
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? "—" : d.toISOString().slice(11, 19);
}
export function dateTime(value: string): string {
  const d = new Date(value);
  return Number.isNaN(d.getTime())
    ? "—"
    : `${d.toISOString().slice(0, 10)} · ${time(value)} UTC`;
}
export function count(value: number): string {
  return new Intl.NumberFormat("en-US").format(value);
}
export function eventLabel(event: SecurityEvent): string {
  return humanize(event.action || event.event_type);
}
export function eventContext(event: SecurityEvent): string {
  return [
    event.actor?.username,
    event.target?.endpoint || event.target?.service,
    event.network?.source_ip,
  ]
    .filter(Boolean)
    .join(" · ");
}
export function evidenceForEntity(
  entity: Entity,
  evidence: Evidence[],
  relationships: Relationship[],
): Evidence[] {
  const ids = new Set(
    relationships
      .filter((r) => r.source === entity.id || r.target === entity.id)
      .flatMap((r) => r.evidence_ids),
  );
  return evidence.filter((item) => ids.has(item.id));
}
