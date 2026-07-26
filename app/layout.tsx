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
  const socialImage = `${origin}/og-v20260726.png`;

  return {
    metadataBase: new URL(origin),
    title: {
      default: "Applied AI Lab",
      template: "%s · Applied AI Lab",
    },
    description:
      "A growing laboratory for honest, production-minded machine learning tools.",
    icons: {
      icon: "/favicon.svg?v=20260726",
      shortcut: "/favicon.svg?v=20260726",
    },
    openGraph: {
      title: "Applied AI Lab",
      description:
        "Real analytical foundations. Working ML tools will appear only when their models are ready.",
      type: "website",
      images: [
        {
          url: socialImage,
          width: 1536,
          height: 1024,
          alt: "Applied AI Lab — Evidence before interface.",
        },
      ],
    },
    twitter: {
      card: "summary_large_image",
      title: "Applied AI Lab",
      description:
        "Real analytical foundations. Working ML tools will appear only when their models are ready.",
      images: [socialImage],
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
