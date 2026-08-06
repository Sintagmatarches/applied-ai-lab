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
      icon: "/favicon.svg?v=20260806-1",
      shortcut: "/favicon.svg?v=20260806-1",
    },
    openGraph: {
      title: "Applied AI Lab",
      description:
        "Working machine-learning tools with honest held-out evidence.",
      type: "website",
      images: [
        {
          url: "/og-v20260730-5.png?v=20260806-1",
          width: 1732,
          height: 909,
          alt: "Applied AI Lab — Olist Delivery Delay Predictor",
        },
      ],
    },
    twitter: {
      card: "summary_large_image",
      title: "Applied AI Lab",
      description:
        "Working machine-learning tools with honest held-out evidence.",
      images: ["/og-v20260730-5.png?v=20260806-1"],
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
