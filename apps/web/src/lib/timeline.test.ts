import { describe, expect, it } from "vitest";
import { groupTimeline } from "./timeline";
import { evidence } from "@/test/fixtures";
import type { Evidence } from "./types";
function request(
  id: string,
  second: number,
  user = "USR-01",
  session = "SES-01",
): Evidence {
  return {
    ...evidence,
    id,
    event_id: `EVT-${id}`,
    timestamp: `2026-09-15T14:11:${String(second).padStart(2, "0")}Z`,
    event: {
      ...evidence.event,
      event_id: `EVT-${id}`,
      action: "request",
      source: "api_gateway",
      actor: { user_id: user },
      session: { session_id: session },
      target: { endpoint: `/internal/${id}` },
    },
  };
}
describe("timeline grouping", () => {
  it("groups a same-principal same-session API burst without dropping or reordering evidence", () => {
    const rows = [request("c", 2), request("a", 0), request("b", 1)];
    const groups = groupTimeline(rows, true);
    expect(groups).toHaveLength(1);
    expect(groups[0].items.map((item) => item.id)).toEqual(["a", "b", "c"]);
    expect(rows[0].id).toBe("c");
  });
  it("does not merge different principals, sessions, missing identities, or non-request events", () => {
    expect(
      groupTimeline([request("a", 0), request("b", 1, "USR-02")], true),
    ).toHaveLength(2);
    expect(
      groupTimeline(
        [request("a", 0), request("b", 1, "USR-01", "SES-02")],
        true,
      ),
    ).toHaveLength(2);
    expect(
      groupTimeline([request("a", 0, "", ""), request("b", 1, "", "")], true),
    ).toHaveLength(2);
    expect(groupTimeline([evidence, request("a", 0)], true)).toHaveLength(2);
  });
  it("preserves annotations and exposes every source row when grouping is off", () => {
    const rows = [
      request("a", 0),
      { ...request("b", 1), relevance: "benign", note: "Reviewed" },
    ];
    expect(groupTimeline(rows, true)[0].items[1].note).toBe("Reviewed");
    expect(groupTimeline(rows, false)).toHaveLength(2);
  });
});
