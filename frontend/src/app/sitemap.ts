import type { MetadataRoute } from "next";

export const dynamic = "force-dynamic";

const SITE_URL = "https://omj-validator.pl";

interface SitemapTask {
  year: string;
  etap: string;
  number: number;
}

interface SitemapData {
  years: string[];
  etaps_by_year: Record<string, string[]>;
  tasks: SitemapTask[];
}

async function getSitemapData(): Promise<SitemapData> {
  const backendUrl = process.env.FASTAPI_URL || "http://localhost:8000";
  const res = await fetch(`${backendUrl}/api/sitemap-data`, {
    next: { revalidate: 86400 },
  });
  return res.json();
}

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const data = await getSitemapData();

  const staticPages: MetadataRoute.Sitemap = [
    {
      url: SITE_URL,
      changeFrequency: "monthly",
      priority: 1.0,
    },
    {
      url: `${SITE_URL}/years`,
      changeFrequency: "yearly",
      priority: 0.9,
    },
    {
      url: `${SITE_URL}/progress`,
      changeFrequency: "monthly",
      priority: 0.7,
    },
    {
      url: `${SITE_URL}/practice/etap2`,
      changeFrequency: "monthly",
      priority: 0.7,
    },
    {
      url: `${SITE_URL}/regulamin`,
      changeFrequency: "yearly",
      priority: 0.3,
    },
  ];

  const yearPages: MetadataRoute.Sitemap = data.years.map((year) => ({
    url: `${SITE_URL}/years/${year}`,
    changeFrequency: "yearly" as const,
    priority: 0.8,
  }));

  const etapPages: MetadataRoute.Sitemap = Object.entries(
    data.etaps_by_year
  ).flatMap(([year, etaps]) =>
    etaps.map((etap) => ({
      url: `${SITE_URL}/years/${year}/${etap}`,
      changeFrequency: "yearly" as const,
      priority: 0.7,
    }))
  );

  const taskPages: MetadataRoute.Sitemap = data.tasks.map((task) => ({
    url: `${SITE_URL}/task/${task.year}/${task.etap}/${task.number}`,
    changeFrequency: "yearly" as const,
    priority: 0.6,
  }));

  return [...staticPages, ...yearPages, ...etapPages, ...taskPages];
}
