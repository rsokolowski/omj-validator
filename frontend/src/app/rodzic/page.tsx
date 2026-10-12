import type { Metadata } from "next";
import { ParentPage } from "@/components/parent/ParentPage";
import { one } from "@/lib/api/serverAccount";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Strona rodzica",
  robots: { index: false, follow: false },
  // Token jest w adresie - nie wysylamy go dalej w naglowku Referer
  referrer: "no-referrer",
};

interface PageProps {
  searchParams: Promise<{ t?: string | string[] }>;
}

export default async function ParentManagePage({ searchParams }: PageProps) {
  const params = await searchParams;
  const token = one(params.t) || null;
  // key: nowy token = nowy stan strony (np. przejscie z /rodzic/zgoda)
  return <ParentPage key={token ?? "none"} token={token} />;
}
