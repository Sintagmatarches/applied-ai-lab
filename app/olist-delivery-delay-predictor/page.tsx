import type { Metadata } from "next";
import { LabShell } from "../lab-shell";

export const metadata: Metadata = {
  title: "Olist Delivery Delay Predictor",
  description:
    "The honest development page for a future Olist delivery-delay prediction model.",
};

export default function OlistDeliveryDelayPredictor() {
  return <LabShell activeProject="olist" />;
}
