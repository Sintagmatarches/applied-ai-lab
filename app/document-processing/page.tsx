import type { Metadata } from "next";
import { LabShell } from "../lab-shell";

export const metadata: Metadata = {
  title: "Document Processing",
  robots: { index: false, follow: false },
};

export default function DocumentProcessing() {
  return <LabShell activeProject="documents" />;
}
