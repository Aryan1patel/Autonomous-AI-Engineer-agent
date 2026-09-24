import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Autonomous AI Engineer",
  description:
    "A LangGraph-powered multi-agent system that plans, codes, executes, debugs, and delivers working FastAPI applications from a single natural-language task.",
  keywords: ["AI", "LangGraph", "code generation", "multi-agent", "FastAPI"],
  openGraph: {
    title: "Autonomous AI Engineer",
    description: "Multi-agent AI that writes, runs, and ships APIs autonomously.",
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
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
      </head>
      <body>{children}</body>
    </html>
  );
}
