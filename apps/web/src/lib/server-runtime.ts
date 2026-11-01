import "server-only";
import { cache } from "react";
import { frontendConfig, publicRuntimeMatches } from "./runtime-config";
import { runtimeCapabilities } from "./capabilities";
import { RuntimeUnavailableError } from "./runtime-unavailable";

export const checkedFrontendConfig = cache(async () => {
  const config = frontendConfig();
  try {
    const response = await fetch(`${config.apiOrigin}/api/runtime`, {
      cache: "no-store",
      redirect: "error",
      signal: AbortSignal.timeout(10000),
    });
    if (!response.ok)
      throw new RuntimeUnavailableError(
        response.status === 429 || response.status === 503
          ? response.headers.get("retry-after")
          : undefined,
      );
    const runtime: unknown = await response.json();
    if (config.publicDemo && !publicRuntimeMatches(runtime)) throw new Error();
    return { ...config, capabilities: runtimeCapabilities(runtime) };
  } catch (error) {
    if (!config.publicDemo)
      return { ...config, capabilities: runtimeCapabilities(null) };
    // Do not expose upstream addresses or networking errors to users or logs.
    throw error instanceof RuntimeUnavailableError
      ? error
      : new RuntimeUnavailableError();
  }
});
