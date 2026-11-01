import { registerHooks } from "node:module";
// Load the facade and its real dependency before installing the redirect.
import "./lint-minimatch.cjs";

// ESLint 9 and its plugins still import minimatch's old callable default API.
// Keep the real patched package installed; adapt only this lint process.
const compatibilityURL = new URL("./lint-minimatch.cjs", import.meta.url).href;

registerHooks({
  resolve(specifier, context, nextResolve) {
    if (specifier === "minimatch") {
      return { url: compatibilityURL, shortCircuit: true };
    }
    return nextResolve(specifier, context);
  },
});
