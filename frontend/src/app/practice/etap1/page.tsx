import type { Metadata } from "next";
import { MockPage } from "../MockPage";

export const metadata: Metadata = {
  title: "Próbny Etap 1",
  description:
    "Sprawdź się w warunkach zbliżonych do części zadaniowej Etapu 1 Olimpiady Matematycznej Juniorów. Zestawy 7 zadań otwartych z limitem czasowym 100 minut.",
  alternates: { canonical: "/practice/etap1" },
};

export const dynamic = "force-dynamic";

export default function MockEtap1Page() {
  return <MockPage etap="etap1" />;
}
