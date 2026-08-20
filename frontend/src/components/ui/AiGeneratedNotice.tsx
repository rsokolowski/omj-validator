// Komponent serwerowy i celowo bez Material-UI: to statyczna adnotacja, więc
// nie potrzebuje ani stanu, ani stylowania przez emotion. Komponenty MUI są
// klienckie, a oznaczenie pojawia się na stronie zadania kilka razy - liczyło
// się to do hydracji i realnie opóźniało moment, w którym klikalne stają się
// odnośniki (breadcrumb). Zwykłe elementy z inline style renderują się w RSC
// i nie dokładają nic do bundla klienta.
import type { CSSProperties } from "react";

/**
 * Widoczne oznaczenie treści generowanych przez AI (art. 50 AI Act).
 *
 * Jeden komponent dla całej aplikacji - nie duplikuj tekstów w innych miejscach.
 * Tekst jest zwykłym tekstem w DOM (czytelny dla czytników ekranu), nie polega
 * na kolorze ani na atrybucie `title`. Ikona jest dekoracyjna (`aria-hidden`).
 *
 * Zasada: JEDNO oznaczenie na sekcję/listę - nie przy każdym elemencie.
 *
 * ```tsx
 * <AiGeneratedNotice variant="evaluation" />                    // pasek nad sekcją
 * <AiGeneratedNotice variant="taskMetadata" display="inline" /> // kompaktowy wiersz
 * ```
 */

export type AiNoticeVariant =
  | "evaluation"
  | "hints"
  | "taskContent"
  | "taskMetadata"
  | "taskListing"
  | "progress";

/** Teksty po polsku, zrozumiałe dla 12-latka. */
const NOTICE_TEXTS: Record<AiNoticeVariant, string> = {
  evaluation: "Ocena i komentarz wygenerowane przez AI — mogą zawierać błędy.",
  hints: "Wskazówki wygenerowane przez AI — mogą zawierać błędy.",
  taskContent:
    "Treść zadania przepisana z PDF-u przez AI — w razie wątpliwości sprawdź oryginalny PDF.",
  taskMetadata:
    "Tytuł zadania przepisała z PDF-u AI. Poziom trudności, kategorie, umiejętności i powiązania zadań też wyznaczyła AI — mogą być niedokładne.",
  taskListing:
    "Treści zadań przepisała z PDF-ów AI, a poziom trudności i kategorie wyznaczyła AI — mogą zawierać błędy.",
  progress:
    "Powiązania między zadaniami, poziom trudności i kategorie wyznaczyła AI — mogą być niedokładne.",
};

// Slate-owe kolory: kontrast tekstu #475569 na #f8fafc to ok. 7:1 (WCAG AAA).
const TEXT_COLOR = "#475569";
const LINK_COLOR = "#1d4ed8";

const BASE_STYLE: CSSProperties = {
  display: "flex",
  alignItems: "flex-start",
  gap: "6px",
  color: TEXT_COLOR,
};

const BLOCK_STYLE: CSSProperties = {
  padding: "8px 12px",
  backgroundColor: "#f8fafc",
  border: "1px solid #e2e8f0",
  borderLeft: "3px solid #94a3b8",
  borderRadius: "4px",
};

const INLINE_STYLE: CSSProperties = {
  flexWrap: "wrap",
};

interface AiGeneratedNoticeProps {
  /** Wariant treści oznaczenia. */
  variant: AiNoticeVariant;
  /** Wariant wizualny: pasek nad sekcją (`block`) lub kompaktowy wiersz (`inline`). */
  display?: "block" | "inline";
  /** Nadpisanie tekstu, jeśli żaden wariant nie pasuje. */
  text?: string;
  /** Dodatkowe style (marginesy w miejscu użycia). */
  style?: CSSProperties;
}

export function AiGeneratedNotice({
  variant,
  display = "block",
  text,
  style,
}: AiGeneratedNoticeProps) {
  const message = text ?? NOTICE_TEXTS[variant];
  const isBlock = display === "block";

  return (
    <div
      role="note"
      style={{
        ...BASE_STYLE,
        ...(isBlock ? BLOCK_STYLE : INLINE_STYLE),
        ...style,
      }}
    >
      {/* Dekoracyjna ikonka "iskierek" - informacja niesiona jest przez tekst */}
      <svg
        aria-hidden="true"
        focusable="false"
        width={isBlock ? 18 : 16}
        height={isBlock ? 18 : 16}
        viewBox="0 0 24 24"
        fill="currentColor"
        style={{ marginTop: "1px", flexShrink: 0 }}
      >
        <path d="M12 2l1.9 5.6L19.5 9.5 13.9 11.4 12 17l-1.9-5.6L4.5 9.5l5.6-1.9L12 2zM18 15l.95 2.8 2.8.95-2.8.95L18 22.5l-.95-2.8-2.8-.95 2.8-.95L18 15z" />
      </svg>
      <p
        style={{
          fontSize: isBlock ? "0.8125rem" : "0.75rem",
          lineHeight: 1.5,
          margin: 0,
        }}
      >
        {message}{" "}
        <a
          href="/regulamin"
          style={{
            color: LINK_COLOR,
            textDecoration: "underline",
            whiteSpace: "nowrap",
          }}
        >
          Więcej w regulaminie
        </a>
      </p>
    </div>
  );
}
