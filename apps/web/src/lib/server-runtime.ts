import "server-only";
import { cache } from "react";
import { frontendConfig, publicRuntimeMatches } from "./runtime-config";

export const checkedFrontendConfig = cache(async () => {
  const config = frontendConfig();
  if (!config.publicDemo) return config;
  try {
    const response = await fetch(`${config.apiOrigin}/api/runtime`, {
      cache: "no-store",
      redirect: "error",
      signal: AbortSignal.timeout(10000),
    });
    if (!response.ok) throw new Error();
    if (!publicRuntimeMatches(await response.json())) throw new Error();
  } catch {
    // Do not expose upstream addresses or networking errors to users or logs.
    throw new Error("Public demo service configuration is unavailable.");
  }
  return config;
});
