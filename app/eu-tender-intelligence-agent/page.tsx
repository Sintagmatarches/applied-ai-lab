import type { Metadata } from "next";
import { headers } from "next/headers";
import { createTenderDateRange } from "../../lib/tender-date-range";
import publicEvidence from "../../artifacts/tender-public-evidence.json";
import { LabShell } from "../lab-shell";
import { TenderIntelligenceDashboard } from "./tender-intelligence-dashboard";

export const metadata: Metadata = {
  title: "EU Tender Intelligence Agent",
  description: "Discover TED opportunities, qualify supplier eligibility deterministically, and monitor procurement changes with evidence.",
  openGraph: { title: "EU Tender Intelligence Agent", description: "Lot-level deterministic qualification and grounded local AI over official TED procurement data.", images: [] },
  twitter: { card: "summary", title: "EU Tender Intelligence Agent", description: "Lot-level deterministic qualification and grounded local AI over official TED procurement data.", images: [] },
};

export default async function EuTenderIntelligenceAgentPage() {
  await headers();
  const defaultDateRange = createTenderDateRange(new Date());

  return <LabShell activeProject="tenders"><TenderIntelligenceDashboard defaultDateRange={defaultDateRange} publicEvidence={publicEvidence} /></LabShell>;
}
