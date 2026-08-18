import type { Metadata } from "next";
import { headers } from "next/headers";
import { createTenderDateRange } from "../../lib/tender-date-range";
import { LabShell } from "../lab-shell";
import { TenderIntelligenceDashboard } from "./tender-intelligence-dashboard";

export const metadata: Metadata = {
  title: "EU Tender Intelligence Agent",
  description: "Discover TED opportunities, qualify supplier eligibility deterministically, and monitor procurement changes with evidence.",
};

export default async function EuTenderIntelligenceAgentPage() {
  await headers();
  const defaultDateRange = createTenderDateRange(new Date());

  return <LabShell activeProject="tenders"><TenderIntelligenceDashboard defaultDateRange={defaultDateRange} /></LabShell>;
}
