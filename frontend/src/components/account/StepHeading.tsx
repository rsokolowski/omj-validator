"use client";

import { Typography } from "@mui/material";
import { ReactNode, useEffect, useRef } from "react";

interface StepHeadingProps {
  children: ReactNode;
  /** Przeniesc fokus na naglowek po zamontowaniu (nowy krok, nowy stan strony) */
  focus?: boolean;
  component?: "h1" | "h2";
}

/**
 * Naglowek kroku. Gdy kroki zmieniaja sie bez przeladowania strony, czytnik
 * ekranu nie wie, ze tresc sie zmienila - przenosimy wiec fokus na nowy
 * naglowek (WCAG 2.4.3, 4.1.3). Montuj z innym `key` dla kazdego kroku.
 */
export function StepHeading({ children, focus = true, component = "h1" }: StepHeadingProps) {
  const ref = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    if (focus) ref.current?.focus();
  }, [focus]);

  return (
    <Typography
      ref={ref}
      variant="h5"
      component={component}
      tabIndex={-1}
      sx={{ fontWeight: 700, color: "grey.900", mb: 1.5, outline: "none", lineHeight: 1.3 }}
    >
      {children}
    </Typography>
  );
}
