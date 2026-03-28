import type { Metadata } from "next";
import { AppRouterCacheProvider } from "@mui/material-nextjs/v15-appRouter";
import { ThemeProvider } from "@/components/providers/ThemeProvider";
import { TimerProvider } from "@/lib/contexts/TimerContext";
import { Header } from "@/components/layout/Header";
import { Footer } from "@/components/layout/Footer";
import { FloatingTimer } from "@/components/practice/FloatingTimer";
import {
  APP_NAME,
  APP_TITLE,
  APP_DESCRIPTION,
  SITE_URL,
} from "@/lib/utils/constants";
import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: APP_TITLE,
    template: `%s | ${APP_NAME}`,
  },
  description: APP_DESCRIPTION,
  metadataBase: new URL(SITE_URL),
  alternates: {
    canonical: "/",
  },
  openGraph: {
    type: "website",
    locale: "pl_PL",
    siteName: APP_NAME,
    title: APP_TITLE,
    description: APP_DESCRIPTION,
    url: SITE_URL,
  },
  twitter: {
    card: "summary",
    title: APP_TITLE,
    description: APP_DESCRIPTION,
  },
  robots: {
    index: true,
    follow: true,
  },
  keywords: [
    "olimpiada matematyczna juniorów",
    "OMJ",
    "matematyka",
    "zadania matematyczne",
    "olimpiada matematyczna",
    "przygotowanie do olimpiady",
    "zadania z matematyki",
    "konkurs matematyczny",
  ],
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "WebSite",
    name: APP_NAME,
    url: SITE_URL,
    description: APP_DESCRIPTION,
    inLanguage: "pl",
    potentialAction: {
      "@type": "SearchAction",
      target: `${SITE_URL}/years`,
    },
  };

  const orgJsonLd = {
    "@context": "https://schema.org",
    "@type": "EducationalOrganization",
    name: APP_NAME,
    url: SITE_URL,
    description:
      "Niekomercyjny projekt edukacyjny pomagający uczniom przygotować się do Olimpiady Matematycznej Juniorów",
  };

  return (
    <html lang="pl">
      <head>
        {/* KaTeX CSS */}
        <link
          rel="stylesheet"
          href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css"
          crossOrigin="anonymous"
        />
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
        />
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(orgJsonLd) }}
        />
      </head>
      <body className="min-h-screen flex flex-col">
        <AppRouterCacheProvider>
          <ThemeProvider>
            <TimerProvider>
              <Header />
              <main className="flex-1 py-8">
                <div className="max-w-[1200px] mx-auto px-6">
                  {children}
                </div>
              </main>
              <Footer />
              <FloatingTimer />
            </TimerProvider>
          </ThemeProvider>
        </AppRouterCacheProvider>
      </body>
    </html>
  );
}
