// @vitest-environment node
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { checkedFrontendConfig } from "./server-runtime";
import { frontendConfig } from "./runtime-config";
import { demoQuestions } from "./demo-questions";
vi.mock("server-only", () => ({}));
vi.mock("react", () => ({ cache: (fn: unknown) => fn }));
vi.mock("./runtime-config", async (original) => ({
  ...(await original<typeof import("./runtime-config")>()),
  frontendConfig: vi.fn(),
}));
const config = vi.mocked(frontendConfig);
const fetcher = vi.fn();
beforeEach(() => {
  vi.resetAllMocks();
  vi.stubGlobal("fetch", fetcher);
});
afterEach(() => vi.unstubAllGlobals());
it("accepts the old safe public contract and fails closed on an unsafe V2 contract", async () => {
  config.mockReturnValue({
    publicDemo: true,
    apiOrigin: "https://api.example.test",
  });
  const runtime = {
    app_mode: "public_demo",
    read_only: true,
    analyst_provider: "deterministic",
    questions: [...demoQuestions],
  };
  fetcher.mockResolvedValueOnce(Response.json(runtime));
  expect((await checkedFrontendConfig()).capabilities).toEqual({});
  fetcher.mockResolvedValueOnce(
    Response.json({
      ...runtime,
      analyst_provider: "openai",
      capabilities: { replay: 1 },
    }),
  );
  await expect(checkedFrontendConfig()).rejects.toThrow(
    "Public demo service configuration is unavailable.",
  );
});
it("obtains local capabilities without exposing private addresses on failure", async () => {
  config.mockReturnValue({
    publicDemo: false,
    apiOrigin: "http://127.0.0.1:8000",
  });
  fetcher.mockResolvedValueOnce(
    Response.json({ capabilities: { replay: 1, evidence_bundle: 1 } }),
  );
  expect((await checkedFrontendConfig()).capabilities).toEqual({
    replay: 1,
    evidence_bundle: 1,
  });
  fetcher.mockRejectedValueOnce(new Error("private networking detail"));
  expect((await checkedFrontendConfig()).capabilities).toEqual({});
});
