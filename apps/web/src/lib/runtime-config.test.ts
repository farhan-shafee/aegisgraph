import { describe, expect, it } from "vitest";
import { frontendConfig, publicRuntimeMatches } from "./runtime-config";
import { demoQuestions } from "./demo-questions";

describe("frontend deployment configuration", () => {
  it("refuses a mismatched backend mode, provider, permission, or question contract", () => {
    const valid = {
      app_mode: "public_demo",
      read_only: true,
      analyst_provider: "deterministic",
      questions: [...demoQuestions],
    };
    expect(publicRuntimeMatches(valid)).toBe(true);
    for (const value of [
      null,
      {},
      { ...valid, app_mode: "local" },
      { ...valid, read_only: false },
      { ...valid, analyst_provider: "openai" },
      { ...valid, questions: ["arbitrary"] },
    ])
      expect(publicRuntimeMatches(value)).toBe(false);
  });
  it("preserves local defaults and does not infer public mode from NODE_ENV", () => {
    expect(frontendConfig({ NODE_ENV: "production" })).toEqual({
      publicDemo: false,
      apiOrigin: "http://127.0.0.1:8000",
    });
  });
  it("requires an explicit HTTPS backend for public mode without exposing rejected values", () => {
    for (const url of [
      undefined,
      "http://api.example.test",
      "https://user:private-value@api.example.test",
      "https://api.example.test?token=private-value",
      "https://api.example.test/path",
      "not-a-url",
    ]) {
      expect(() =>
        frontendConfig({ APP_MODE: "public_demo", API_INTERNAL_URL: url }),
      ).toThrow();
      try {
        frontendConfig({ APP_MODE: "public_demo", API_INTERNAL_URL: url });
      } catch (error) {
        expect(String(error)).not.toContain("private-value");
      }
    }
    expect(
      frontendConfig({
        APP_MODE: "public_demo",
        API_INTERNAL_URL: "https://api.example.test",
      }),
    ).toEqual({ publicDemo: true, apiOrigin: "https://api.example.test" });
    expect(() => frontendConfig({ APP_MODE: "public" })).toThrow(
      "APP_MODE must be local or public_demo.",
    );
  });
});
