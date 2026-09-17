"use client";
import { createContext, useContext } from "react";

const DemoMode = createContext(false);
export function DemoModeProvider({
  publicDemo,
  children,
}: {
  publicDemo: boolean;
  children: React.ReactNode;
}) {
  return <DemoMode.Provider value={publicDemo}>{children}</DemoMode.Provider>;
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
