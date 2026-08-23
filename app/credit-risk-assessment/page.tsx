import type { Metadata } from "next";
import { LabShell } from "../lab-shell";

export const metadata: Metadata = {
  title: "Credit Risk Assessment",
  robots: { index: false, follow: false },
};

export default function CreditRiskAssessment() {
  return <LabShell activeProject="credit" />;
}
