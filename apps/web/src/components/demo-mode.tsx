"use client";
import { createContext, useContext } from "react";
import type { Capabilities, Capability } from "@/lib/capabilities";

const DemoMode = createContext(false);
const RuntimeCapabilities = createContext<Capabilities>({});
export function DemoModeProvider({
  publicDemo,
  capabilities = {},
  children,
}: {
  publicDemo: boolean;
  capabilities?: Capabilities;
  children: React.ReactNode;
}) {
  return (
    <DemoMode.Provider value={publicDemo}>
      <RuntimeCapabilities.Provider value={capabilities}>
        {children}
      </RuntimeCapabilities.Provider>
    </DemoMode.Provider>
  );
}
export function useCapability(name: Capability) {
  return useContext(RuntimeCapabilities)[name] === 1;
}
export function usePublicDemo() {
  return useContext(DemoMode);
}

export function ReadOnlyNotice() {
  return (
    <p className="read-only-note">
      Read-only public demo. Case changes and approvals are available in the
      local interview workflow.
    </p>
  );
}
