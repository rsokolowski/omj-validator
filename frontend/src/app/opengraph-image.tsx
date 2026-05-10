import { ImageResponse } from "next/og";
import { APP_NAME, APP_DESCRIPTION } from "@/lib/utils/constants";

export const alt = APP_NAME;
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function OpengraphImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          alignItems: "flex-start",
          padding: "80px",
          background:
            "linear-gradient(135deg, #1e3a8a 0%, #3b82f6 50%, #60a5fa 100%)",
          color: "white",
          fontFamily: "sans-serif",
        }}
      >
        <div
          style={{
            fontSize: 40,
            fontWeight: 600,
            opacity: 0.85,
            marginBottom: 24,
            letterSpacing: "-0.02em",
          }}
        >
          Trener OMJ
        </div>
        <div
          style={{
            fontSize: 76,
            fontWeight: 800,
            lineHeight: 1.1,
            marginBottom: 32,
            letterSpacing: "-0.03em",
          }}
        >
          Olimpiada Matematyczna Juniorów
        </div>
        <div
          style={{
            fontSize: 32,
            opacity: 0.9,
            lineHeight: 1.3,
            maxWidth: 1000,
          }}
        >
          {APP_DESCRIPTION}
        </div>
        <div
          style={{
            fontSize: 28,
            opacity: 0.75,
            marginTop: "auto",
            display: "flex",
            alignItems: "center",
            gap: 16,
          }}
        >
          <span>340+ zadań</span>
          <span>·</span>
          <span>Ocena AI</span>
          <span>·</span>
          <span>omj-validator.pl</span>
        </div>
      </div>
    ),
    { ...size }
  );
}
