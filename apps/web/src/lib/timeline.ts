import type { Evidence } from "./types";
export interface TimelineGroup {
  id: string;
  items: Evidence[];
}
export function groupTimeline(
  evidence: Evidence[],
  compact: boolean,
): TimelineGroup[] {
  const sorted = evidence
    .slice()
    .sort((a, b) => Date.parse(a.timestamp) - Date.parse(b.timestamp));
  const groups: TimelineGroup[] = [];
  for (const item of sorted) {
    const previous = groups.at(-1),
      first = previous?.items[0];
    const sameBurst =
      compact &&
      first?.event.action === "request" &&
      item.event.action === "request" &&
      first.event.source === item.event.source &&
      Boolean(first.event.actor?.user_id) &&
      Boolean(first.event.session?.session_id) &&
      first.event.actor?.user_id === item.event.actor?.user_id &&
      first.event.session?.session_id === item.event.session?.session_id &&
      Date.parse(item.timestamp) - Date.parse(first.timestamp) <= 60000;
    if (sameBurst && previous) previous.items.push(item);
    else groups.push({ id: item.id, items: [item] });
  }
  return groups;
}
