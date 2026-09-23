import { render, screen } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import ReplayPage from "./page";
import { checkedFrontendConfig } from "@/lib/server-runtime";
import { serverApi } from "@/lib/server-api";

vi.mock("@/lib/server-runtime", () => ({ checkedFrontendConfig: vi.fn() }));
vi.mock("@/lib/server-api", () => ({ serverApi: vi.fn() }));
vi.mock("@/components/scenario-replay", () => ({
  ScenarioReplay: ({ initialScenarioId }: { initialScenarioId: string }) => (
    <p>Selected: {initialScenarioId}</p>
  ),
}));
beforeEach(() => vi.clearAllMocks());

it("retains investigation access without fetching an unadvertised replay API", async () => {
  vi.mocked(checkedFrontendConfig).mockResolvedValue({
    publicDemo: true,
    apiOrigin: "http://example.invalid",
    capabilities: {},
  });
  render(await ReplayPage({ searchParams: Promise.resolve({}) }));
  expect(
    screen.getByText("Replay is unavailable on this backend version"),
  ).toBeVisible();
  expect(
    screen.getByRole("link", { name: "Open investigations" }),
  ).toHaveAttribute("href", "/incidents");
  expect(serverApi).not.toHaveBeenCalled();
});

it("passes a scenario query to the catalog-backed selection", async () => {
  vi.mocked(checkedFrontendConfig).mockResolvedValue({
    publicDemo: true,
    apiOrigin: "http://example.invalid",
    capabilities: { scenarios: 1, replay: 1 },
  });
  vi.mocked(serverApi).mockResolvedValue({ items: [] });
  render(
    await ReplayPage({
      searchParams: Promise.resolve({ scenario: "isolated-anomaly" }),
    }),
  );
  expect(screen.getByText("Selected: isolated-anomaly")).toBeVisible();
  expect(serverApi).toHaveBeenCalledWith("/scenarios");
});

it("renders the established unavailable state when the scenario catalog cannot be read", async () => {
  vi.mocked(checkedFrontendConfig).mockResolvedValue({
    publicDemo: true,
    apiOrigin: "http://example.invalid",
    capabilities: { scenarios: 1, replay: 1 },
  });
  vi.mocked(serverApi).mockRejectedValue(new Error("Unavailable"));
  render(await ReplayPage({ searchParams: Promise.resolve({}) }));
  expect(screen.getByRole("alert")).toHaveTextContent(
    "Unable to load workspace data",
  );
});
