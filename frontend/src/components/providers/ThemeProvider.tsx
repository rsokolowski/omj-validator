"use client";

import { ThemeProvider as MuiThemeProvider, createTheme } from "@mui/material/styles";
import CssBaseline from "@mui/material/CssBaseline";
import { ReactNode } from "react";

// Dodatkowa rola koloru w palecie (fiolet akcentowy). Trzymamy ja w motywie,
// zeby komponenty nie zapisywaly wartosci szesnastkowych u siebie.
declare module "@mui/material/styles" {
  interface Palette {
    accent: Palette["primary"];
  }
  interface PaletteOptions {
    accent?: PaletteOptions["primary"];
  }
}

// UWAGA (WCAG 1.4.3 / 1.4.11): wartosci ponizej sa dobrane tak, zeby tekst
// w tym kolorze mial co najmniej 4,5:1 na bialym tle karty (#fff) oraz na tle
// strony (#f9fafb). Przy zmianie odcienia przelicz kontrast, zanim wdrozysz.
const theme = createTheme({
  palette: {
    primary: {
      main: "#2563eb",
      light: "#3b82f6",
      dark: "#1d4ed8",
    },
    secondary: {
      main: "#6b7280",
      light: "#9ca3af",
      dark: "#4b5563",
    },
    error: {
      // 4,83:1 na bialym
      main: "#dc2626",
    },
    warning: {
      // 5,02:1 na bialym (bylo #d97706 = 3,19:1)
      main: "#b45309",
    },
    success: {
      // 5,48:1 na bialym (bylo #059669 = 3,77:1)
      main: "#047857",
    },
    accent: {
      // 7,10:1 na bialym; bialy tekst na tym tle 7,10:1
      main: "#6d28d9",
      light: "#f5f3ff",
      dark: "#5b21b6",
      contrastText: "#ffffff",
    },
    grey: {
      50: "#f9fafb",
      100: "#f3f4f6",
      200: "#e5e7eb",
      300: "#d1d5db",
      400: "#9ca3af",
      500: "#6b7280",
      600: "#4b5563",
      700: "#374151",
      800: "#1f2937",
      900: "#111827",
    },
    background: {
      default: "#f9fafb",
      paper: "#ffffff",
    },
  },
  typography: {
    fontFamily: [
      "-apple-system",
      "BlinkMacSystemFont",
      '"Segoe UI"',
      "Roboto",
      '"Helvetica Neue"',
      "Arial",
      "sans-serif",
    ].join(","),
    h1: {
      fontSize: "2rem",
      fontWeight: 700,
      lineHeight: 1.3,
    },
    h2: {
      fontSize: "1.5rem",
      fontWeight: 600,
      lineHeight: 1.3,
    },
    h3: {
      fontSize: "1.25rem",
      fontWeight: 600,
      lineHeight: 1.3,
    },
    body1: {
      fontSize: "1rem",
      lineHeight: 1.6,
    },
    body2: {
      fontSize: "0.875rem",
      lineHeight: 1.6,
    },
  },
  shape: {
    borderRadius: 8,
  },
  components: {
    MuiButton: {
      styleOverrides: {
        root: {
          textTransform: "none",
          fontWeight: 500,
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          boxShadow: "0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1)",
        },
      },
    },
    MuiChip: {
      styleOverrides: {
        root: {
          fontWeight: 500,
        },
      },
    },
  },
});

interface ThemeProviderProps {
  children: ReactNode;
}

export function ThemeProvider({ children }: ThemeProviderProps) {
  return (
    <MuiThemeProvider theme={theme}>
      <CssBaseline />
      {children}
    </MuiThemeProvider>
  );
}
