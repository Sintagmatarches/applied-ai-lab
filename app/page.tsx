import type { Metadata } from "next";
import { LabShell } from "./lab-shell";

export const metadata: Metadata = {
  title: "Applied AI Lab",
  description:
    "A growing laboratory for honest, production-minded machine learning tools.",
};

export default function Home() {
  return <LabShell activeProject="home" />;
}
