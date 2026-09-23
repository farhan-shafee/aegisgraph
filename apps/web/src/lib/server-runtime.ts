import "server-only";
import { cache } from "react";
import { frontendConfig, publicRuntimeMatches } from "./runtime-config";
import { runtimeCapabilities } from "./capabilities";

export const checkedFrontendConfig = cache(async () => {
  const config = frontendConfig();
  try {
    const response = await fetch(`${config.apiOrigin}/api/runtime`, {
      cache: "no-store",
      redirect: "error",
      signal: AbortSignal.timeout(10000),
    });
    if (!response.ok) throw new Error();
    const runtime: unknown = await response.json();
    if (config.publicDemo && !publicRuntimeMatches(runtime)) throw new Error();
    return { ...config, capabilities: runtimeCapabilities(runtime) };
  } catch {
    if (!config.publicDemo)
      return { ...config, capabilities: runtimeCapabilities(null) };
    // Do not expose upstream addresses or networking errors to users or logs.
    throw new Error("Public demo service configuration is unavailable.");
  }
});
