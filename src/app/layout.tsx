import type { Metadata } from "next";
import "./globals.css";
import ZeusChatWidget from "@/components/chat/ZeusChatWidget";

export const metadata: Metadata = {
  title: "KiSTI — Edge Telemetry Platform",
  description:
    "Real-time edge telemetry for motorsport. Sensor fusion, CAN bus aggregation, and AI-powered diagnostics on NVIDIA Jetson.",
  openGraph: {
    title: "KiSTI — Make Data Speak Racer",
    description:
      "Edge telemetry platform demo — 2014 Subaru STI with Link ECU + Jetson Orin",
    siteName: "KiSTI by ALDC",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="min-h-screen antialiased">
        {children}
        <ZeusChatWidget />
      </body>
    </html>
  );
}
