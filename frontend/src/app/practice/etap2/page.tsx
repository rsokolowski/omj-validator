import type { Metadata } from "next";
import { MockPage } from "../MockPage";

export const metadata: Metadata = {
  title: "Próbny Etap 2",
  description:
    "Sprawdź się w warunkach zbliżonych do prawdziwego Etapu 2 Olimpiady Matematycznej Juniorów. Zestawy 5 zadań z limitem czasowym 3 godzin.",
  alternates: { canonical: "/practice/etap2" },
};

export const dynamic = "force-dynamic";

export default function MockEtap2Page() {
  return <MockPage etap="etap2" />;
}
