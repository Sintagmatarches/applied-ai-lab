import type { Metadata } from "next";
import { LabShell } from "./lab-shell";

export const metadata: Metadata = {
  title: "Applied AI Lab",
  description:
    "Evidence-backed machine learning, analytics engineering and BI projects built to be inspected.",
};

export default function Home() {
  return <LabShell activeProject="home" />;
}
