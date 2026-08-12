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
      "Evidence-backed machine learning, analytics engineering and BI projects built to be inspected.",
    icons: {
      icon: "/favicon.svg?v=20260812-rail-regions-1",
      shortcut: "/favicon.svg?v=20260812-rail-regions-1",
    },
    openGraph: {
      title: "Applied AI Lab",
      description:
        "Machine learning, analytics engineering and BI projects with reproducible evidence.",
      type: "website",
      images: [
        {
          url: "/og.png?v=20260812-rail-regions-1",
          width: 1731,
          height: 909,
          alt: "Applied AI Lab — Olist Delivery Delay Predictor and Finland Rail Monitoring System",
        },
      ],
    },
    twitter: {
      card: "summary_large_image",
      title: "Applied AI Lab",
      description:
        "Machine learning, analytics engineering and BI projects with reproducible evidence.",
      images: ["/og.png?v=20260812-rail-regions-1"],
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
