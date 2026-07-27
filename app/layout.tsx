import type { Metadata } from "next";
import { headers } from "next/headers";
import "./globals.css";

export async function generateMetadata(): Promise<Metadata> {
  const requestHeaders = await headers();
  const host = requestHeaders.get("x-forwarded-host") ?? requestHeaders.get("host");
  const forwardedProtocol = requestHeaders.get("x-forwarded-proto");
  const protocol =
    forwardedProtocol ?? (host?.startsWith("localhost") ? "http" : "https");
  const origin = host ? `${protocol}://${host}` : "https://applied-ai-lab.invalid";

  return {
    metadataBase: new URL(origin),
    title: {
      default: "Applied AI Lab",
      template: "%s · Applied AI Lab",
    },
    description:
      "A growing laboratory for honest, production-minded machine learning tools.",
    icons: {
      icon: "/favicon.svg?v=20260727-5",
      shortcut: "/favicon.svg?v=20260727-5",
    },
    openGraph: {
      title: "Applied AI Lab",
      description:
        "Real analytical foundations. Working ML tools will appear only when their models are ready.",
      type: "website",
    },
    twitter: {
      card: "summary",
      title: "Applied AI Lab",
      description:
        "Real analytical foundations. Working ML tools will appear only when their models are ready.",
    },
  };
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
