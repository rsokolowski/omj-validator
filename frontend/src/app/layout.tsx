import type { Metadata, Viewport } from "next";
import { AppRouterCacheProvider } from "@mui/material-nextjs/v15-appRouter";
import { ThemeProvider } from "@/components/providers/ThemeProvider";
import { TimerProvider } from "@/lib/contexts/TimerContext";
import { Header } from "@/components/layout/Header";
import { AccountGate } from "@/components/account/AccountGate";
import { Footer } from "@/components/layout/Footer";
import { FloatingTimer } from "@/components/practice/FloatingTimer";
import { ExerciseBatchProvider } from "@/components/patterns/ExerciseBatchProvider";
import {
  APP_NAME,
  APP_TITLE,
  APP_DESCRIPTION,
  SITE_URL,
} from "@/lib/utils/constants";
import "katex/dist/katex.min.css";
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
    card: "summary_large_image",
    title: APP_TITLE,
    description: APP_DESCRIPTION,
  },
  robots: {
    index: true,
    follow: true,
  },
  // Installed on the iPhone home screen it opens without Safari's bars
  // (needed there for the reminders, see app/manifest.ts)
  appleWebApp: {
    capable: true,
    title: APP_NAME,
    statusBarStyle: "default",
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

export const viewport: Viewport = {
  themeColor: "#2563eb",
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
  };

  const orgJsonLd = {
    "@context": "https://schema.org",
    "@type": "EducationalOrganization",
    name: APP_NAME,
    url: SITE_URL,
    description:
      "Niekomercyjny projekt edukacyjny pomagający przygotować się do Olimpiady Matematycznej Juniorów",
  };

  return (
    <html lang="pl">
      <head>
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
        {/* WCAG 2.4.1: pierwszy element w kolejnosci tabulacji, widoczny
            dopiero po otrzymaniu fokusu (style w globals.css). */}
        <a href="#tresc-glowna" className="skip-link">
          Przejdź do treści głównej
        </a>
        <AppRouterCacheProvider>
          <ThemeProvider>
            <TimerProvider>
              <ExerciseBatchProvider>
                <Header />
                <AccountGate />
                <main id="tresc-glowna" tabIndex={-1} className="flex-1 py-8">
                  <div className="max-w-[1200px] mx-auto px-6">
                    {children}
                  </div>
                </main>
                <Footer />
                <FloatingTimer />
              </ExerciseBatchProvider>
            </TimerProvider>
          </ThemeProvider>
        </AppRouterCacheProvider>
      </body>
    </html>
  );
}
