// Server configuration only. Never import this module into client components.
import { demoQuestions } from "./demo-questions";

export function publicRuntimeMatches(value: unknown): boolean {
  if (!value || typeof value !== "object") return false;
  const runtime = value as Record<string, unknown>;
  return (
    runtime.app_mode === "public_demo" &&
    runtime.read_only === true &&
    runtime.analyst_provider === "deterministic" &&
    Array.isArray(runtime.questions) &&
    runtime.questions.length === demoQuestions.length &&
    demoQuestions.every((question) =>
      (runtime.questions as unknown[]).includes(question),
    )
  );
}

export function frontendConfig(
  env: Record<string, string | undefined> = process.env,
) {
  const mode = env.APP_MODE || "local";
  if (mode !== "local" && mode !== "public_demo")
    throw new Error("APP_MODE must be local or public_demo.");
  const publicDemo = mode === "public_demo";
  const value =
    env.API_INTERNAL_URL || (publicDemo ? "" : "http://127.0.0.1:8000");
  let url: URL;
  try {
    url = new URL(value);
  } catch {
    throw new Error("A valid API_INTERNAL_URL is required.");
  }
  if (
    !["http:", "https:"].includes(url.protocol) ||
    url.username ||
    url.password ||
    url.search ||
    url.hash ||
    url.pathname !== "/" ||
    (publicDemo && url.protocol !== "https:")
  )
    throw new Error(
      "API_INTERNAL_URL must be an origin without credentials; public_demo requires HTTPS.",
    );
  return { publicDemo, apiOrigin: url.origin };
}
