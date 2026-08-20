import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";
import jsxA11y from "eslint-plugin-jsx-a11y";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  // Dostępność (WCAG). Domyślna konfiguracja Next.js włącza tylko sześć
  // najprostszych reguł jsx-a11y (atrybut `alt`, poprawność atrybutów ARIA),
  // a reguły klawiaturowe analizują wyłącznie elementy DOM. W tym projekcie
  // procedury obsługi zdarzeń wiszą na komponentach Material-UI, więc bez
  // mapowania `settings["jsx-a11y"].components` linter nie widział NICZEGO.
  // Uwaga: wtyczka jsx-a11y jest juz zarejestrowana przez eslint-config-next,
  // wiec podajemy tylko `settings` i `rules` (ponowne podanie `plugins`
  // konczy sie bledem "Cannot redefine plugin").
  {
    files: ["src/**/*.{ts,tsx}"],
    settings: {
      "jsx-a11y": {
        components: {
          // Uwaga: `Chip` celowo NIE jest mapowany. MUI renderuje go raz jako
          // <div>, a raz (gdy ma `onClick`) jako <button> z wlasnym
          // `tabIndex` - sztywne mapowanie dawaloby falszywe alarmy.
          Box: "div",
          Paper: "div",
          Card: "div",
          CardContent: "div",
          Container: "div",
          Typography: "p",
          Button: "button",
          IconButton: "button",
          MuiLink: "a",
          Link: "a",
        },
      },
    },
    rules: {
      ...jsxA11y.flatConfigs.recommended.rules,
      "jsx-a11y/click-events-have-key-events": "error",
      "jsx-a11y/no-static-element-interactions": "error",
      "jsx-a11y/no-noninteractive-element-interactions": "error",
      "jsx-a11y/interactive-supports-focus": "error",
      "jsx-a11y/label-has-associated-control": "error",
      "jsx-a11y/anchor-is-valid": "error",
      // `ignoreNonDOM`: autoFocus na polu wewnatrz MUI <Dialog> to poprawny
      // wzorzec (fokus ma wejsc do okna dialogowego), a regula nie widzi
      // kontekstu. Na surowych elementach DOM regula dziala dalej.
      "jsx-a11y/no-autofocus": ["error", { ignoreNonDOM: true }],
    },
  },
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),
]);

export default eslintConfig;
