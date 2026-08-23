import type { Metadata } from "next";
import { LabShell } from "../lab-shell";

export const metadata: Metadata = {
  title: "Housing Value Forecast",
  robots: { index: false, follow: false },
};

export default function HousingValueForecast() {
  return <LabShell activeProject="housing" />;
}
