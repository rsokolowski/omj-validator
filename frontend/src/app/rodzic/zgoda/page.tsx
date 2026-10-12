import type { Metadata } from "next";
import { ParentConsent } from "@/components/parent/ParentConsent";
import { one } from "@/lib/api/serverAccount";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Zgoda rodzica",
  robots: { index: false, follow: false },
  // Token jest w adresie - nie wysylamy go dalej w naglowku Referer
  referrer: "no-referrer",
};

interface PageProps {
  searchParams: Promise<{ t?: string | string[]; decyzja?: string | string[] }>;
}

export default async function ParentConsentPage({ searchParams }: PageProps) {
  const params = await searchParams;
  return <ParentConsent token={one(params.t) || null} declineIntent={one(params.decyzja) === "nie"} />;
}
