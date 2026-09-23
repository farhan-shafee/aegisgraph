import type { Metadata } from "next";
import { Shell } from "@/components/shell";
import { DemoModeProvider } from "@/components/demo-mode";
import { checkedFrontendConfig } from "@/lib/server-runtime";
import "./globals.css";
// Deployment mode and the backend contract are checked per request, not at build time.
export const dynamic = "force-dynamic";
export const metadata: Metadata = {
  title: {
    default: "AegisGraph · Security investigations",
    template: "%s · AegisGraph",
  },
  description:
    "Evidence-grounded security investigations for a simulated fintech environment.",
  robots: { index: false, follow: false },
};
export default async function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  const { publicDemo, capabilities } = await checkedFrontendConfig();
  return (
    <html lang="en">
      <body>
        <DemoModeProvider publicDemo={publicDemo} capabilities={capabilities}>
          <Shell>{children}</Shell>
        </DemoModeProvider>
      </body>
    </html>
  );
}
