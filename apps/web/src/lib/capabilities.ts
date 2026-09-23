export const capabilityNames = [
  "scenarios",
  "replay",
  "rule_workbench",
  "hypotheses",
  "analyst_benchmark",
  "evidence_bundle",
] as const;
export type Capability = (typeof capabilityNames)[number];
export type Capabilities = Partial<Record<Capability, 1>>;

export function runtimeCapabilities(value: unknown): Capabilities {
  if (!value || typeof value !== "object" || !("capabilities" in value))
    return {};
  const source = value.capabilities;
  if (!source || typeof source !== "object" || Array.isArray(source)) return {};
  return Object.fromEntries(
    capabilityNames
      .filter(
        (key) => Object.hasOwn(source, key) && Reflect.get(source, key) === 1,
      )
      .map((key) => [key, 1]),
  );
}
