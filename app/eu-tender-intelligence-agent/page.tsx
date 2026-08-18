import type { Metadata } from "next";
import { LabShell } from "../lab-shell";
import { TenderIntelligenceDashboard } from "./tender-intelligence-dashboard";

export const metadata: Metadata = {
  title: "EU Tender Intelligence Agent",
  description: "Discover TED opportunities, qualify supplier eligibility deterministically, and monitor procurement changes with evidence.",
};

export default function EuTenderIntelligenceAgentPage() {
  return <LabShell activeProject="tenders"><TenderIntelligenceDashboard /></LabShell>;
}
