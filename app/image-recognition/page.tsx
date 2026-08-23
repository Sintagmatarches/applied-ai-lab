import type { Metadata } from "next";
import { LabShell } from "../lab-shell";

export const metadata: Metadata = {
  title: "Image Recognition",
  robots: { index: false, follow: false },
};

export default function ImageRecognition() {
  return <LabShell activeProject="vision" />;
}
