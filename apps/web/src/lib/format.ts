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
  const attributes = event.attributes || {};
  if (event.action === "login") {
    if (event.outcome !== "success") return "Unsuccessful sign-in";
    if (
      attributes.device_previously_seen === false ||
      event.device?.trusted === false
    )
      return "Sign-in from an unrecognized device";
    if (event.device?.trusted === true)
      return "Sign-in from a recognized device";
    return "Successful sign-in";
  }
  if (event.action === "mfa_accept") return "MFA challenge accepted";
  if (event.action === "role_assign")
    return attributes.new_role === "platform_admin"
      ? "Privileged role assigned"
      : "Role assigned";
  if (event.action === "role_revert") return "Previous role restored";
  if (event.action === "read_sensitive")
    return "Sensitive account resource accessed";
  if (
    event.action === "query" &&
    typeof attributes.records_accessed === "number"
  )
    return `Account query accessed ${count(attributes.records_accessed)} records`;
  if (event.action === "request") return "Internal API request";
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
