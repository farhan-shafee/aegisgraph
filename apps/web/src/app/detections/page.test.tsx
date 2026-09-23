import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { checkedFrontendConfig } from "@/lib/server-runtime";
import { serverApi } from "@/lib/server-api";
import DetectionsPage from "./page";
import DetectionPage from "./[id]/page";

vi.mock("@/lib/server-runtime", () => ({ checkedFrontendConfig: vi.fn() }));
vi.mock("@/lib/server-api", () => ({ serverApi: vi.fn() }));
vi.mock("next/navigation", () => ({
  notFound: () => {
    throw new Error("Not found");
  },
}));
vi.mock("@/components/detection-workbench", () => ({
  DetectionWorkbench: ({ initial }: { initial: { rule: { id: string } } }) => (
    <div>Workbench {initial.rule.id}</div>
  ),
}));

const rule = {
  id: "APP-002",
  name: "Abnormal account data volume",
  kind: "data_volume",
  description: "Synthetic query volume",
  severity: "high",
  enabled: true,
  threshold: 1000,
  window_minutes: 0,
  alert_count: 1,
};

beforeEach(() => {
  vi.mocked(serverApi).mockReset();
  vi.mocked(checkedFrontendConfig).mockReset();
  vi.mocked(checkedFrontendConfig).mockResolvedValue({
    publicDemo: true,
    apiOrigin: "https://api.example.test",
    capabilities: {},
  });
});

describe("detection page rollout compatibility", () => {
  it("keeps the historical rule library available without new-feature links", async () => {
    vi.mocked(serverApi).mockResolvedValue({ items: [rule] });
    render(await DetectionsPage());
    expect(screen.getByText("APP-002")).toBeVisible();
    expect(
      screen.getByRole("columnheader", { name: "Historical alerts" }),
    ).toBeVisible();
    expect(
      screen.queryByRole("link", { name: /workbench/i }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: "APP-002" }),
    ).not.toBeInTheDocument();
  });

  it("does not request an unsupported workbench during a staggered rollout", async () => {
    render(await DetectionPage({ params: Promise.resolve({ id: "APP-002" }) }));
    expect(
      screen.getByText(/does not yet advertise this feature/i),
    ).toBeVisible();
    expect(
      screen.getByRole("link", { name: "Return to the rule library" }),
    ).toBeVisible();
    expect(serverApi).not.toHaveBeenCalled();
  });

  it("loads a typed workbench only when its capability is advertised", async () => {
    vi.mocked(checkedFrontendConfig).mockResolvedValue({
      publicDemo: true,
      apiOrigin: "https://api.example.test",
      capabilities: { rule_workbench: 1 },
    });
    vi.mocked(serverApi).mockResolvedValue({ rule });
    render(await DetectionPage({ params: Promise.resolve({ id: "APP-002" }) }));
    expect(screen.getByText("Workbench APP-002")).toBeVisible();
    expect(serverApi).toHaveBeenCalledWith("/detections/APP-002/workbench");
  });
});
