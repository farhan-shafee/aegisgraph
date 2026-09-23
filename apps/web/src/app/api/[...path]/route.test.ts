// @vitest-environment node
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { GET, PATCH, POST } from "./route";
import { checkedFrontendConfig } from "@/lib/server-runtime";
vi.mock("@/lib/server-runtime", () => ({ checkedFrontendConfig: vi.fn() }));
const check = vi.mocked(checkedFrontendConfig);
const fetcher = vi.fn();
const context = (path: string[]) => ({ params: Promise.resolve({ path }) });
beforeEach(() => {
  vi.clearAllMocks();
  vi.stubGlobal("fetch", fetcher);
  check.mockResolvedValue({
    publicDemo: true,
    apiOrigin: "https://api.example.test",
    capabilities: {},
  });
});
afterEach(() => vi.unstubAllGlobals());

it("denies persistent writes and missing origins before forwarding a public request", async () => {
  const patch = await PATCH(
    new Request("https://demo.example.test/api/incidents/INC-1", {
      method: "PATCH",
    }),
    context(["incidents", "INC-1"]),
  );
  const post = await POST(
    new Request("https://demo.example.test/api/incidents/INC-1/analysis", {
      method: "POST",
    }),
    context(["incidents", "INC-1", "analysis"]),
  );
  expect(patch.status).toBe(403);
  expect(post.status).toBe(403);
  expect(fetcher).not.toHaveBeenCalled();
});

it("forwards the actual origin and JSON but strips authorization and cookies", async () => {
  fetcher.mockResolvedValue(
    Response.json({ status: "answered", provider: "deterministic" }),
  );
  const body = JSON.stringify({ question: "What most likely happened?" });
  const response = await POST(
    new Request("https://demo.example.test/api/incidents/INC-1/analysis", {
      method: "POST",
      headers: {
        Origin: "https://demo.example.test",
        "Content-Type": "application/json",
        Authorization: "private-test-value",
        Cookie: "private-test-cookie",
      },
      body,
    }),
    context(["incidents", "INC-1", "analysis"]),
  );
  expect(response.status).toBe(200);
  const [url, options] = fetcher.mock.calls[0];
  expect(url).toBe("https://api.example.test/api/incidents/INC-1/analysis");
  expect(options.headers.get("Origin")).toBe("https://demo.example.test");
  expect(options.headers.has("Authorization")).toBe(false);
  expect(options.headers.has("Cookie")).toBe(false);
  expect(new TextDecoder().decode(options.body)).toBe(body);
  expect(response.headers.get("cache-control")).toBe("no-store");
});

it("bounds streamed bodies and masks upstream errors and addresses", async () => {
  const oversized = await POST(
    new Request("https://demo.example.test/api/incidents/INC-1/analysis", {
      method: "POST",
      headers: {
        Origin: "https://demo.example.test",
        "Content-Type": "application/json",
      },
      body: "a".repeat(65537),
    }),
    context(["incidents", "INC-1", "analysis"]),
  );
  expect(oversized.status).toBe(413);
  expect(fetcher).not.toHaveBeenCalled();
  fetcher.mockRejectedValue(
    new Error("https://private-backend.example.test internal detail"),
  );
  const failed = await GET(
    new Request("https://demo.example.test/api/overview"),
    context(["overview"]),
  );
  expect(failed.status).toBe(503);
  expect(await failed.text()).not.toContain("private-backend");
  check.mockRejectedValue(new Error("backend mode mismatch"));
  fetcher.mockClear();
  expect(
    (
      await GET(
        new Request("https://demo.example.test/api/overview"),
        context(["overview"]),
      )
    ).status,
  ).toBe(503);
  expect(fetcher).not.toHaveBeenCalled();
});

it("retains local writes while refusing path traversal and upstream redirects", async () => {
  check.mockResolvedValue({
    publicDemo: false,
    apiOrigin: "http://127.0.0.1:8000",
    capabilities: {},
  });
  fetcher.mockResolvedValue(Response.json({ status: "investigating" }));
  const response = await PATCH(
    new Request("http://127.0.0.1:3000/api/incidents/INC-1", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: "investigating" }),
    }),
    context(["incidents", "INC-1"]),
  );
  expect(response.status).toBe(200);
  expect(fetcher.mock.calls[0][1].redirect).toBe("error");
  fetcher.mockClear();
  expect(
    (
      await GET(
        new Request("http://127.0.0.1:3000/api/overview"),
        context(["..", "private"]),
      )
    ).status,
  ).toBe(404);
  expect(fetcher).not.toHaveBeenCalled();
});
