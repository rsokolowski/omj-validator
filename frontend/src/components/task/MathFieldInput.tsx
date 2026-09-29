"use client";

import { useEffect, useRef } from "react";
import { MathfieldElement } from "mathlive";

// Self-hosted assets, copied by scripts/copy-editor-assets.mjs. Without this
// MathLive resolves "./fonts" against its own chunk URL (a 404 under Next) and
// falls back to nothing useful; sounds are off entirely.
MathfieldElement.fontsDirectory = "/mathlive/fonts";
MathfieldElement.soundsDirectory = null;
if (typeof window !== "undefined") {
  if (!window.customElements.get("math-field")) {
    window.customElements.define("math-field", MathfieldElement);
  }
  // The virtual keyboard is a panel appended to <body> at z-index 105 by
  // default - under MUI's modal (1300), i.e. behind the dialog's backdrop.
  document.body.style.setProperty("--keyboard-zindex", "1350");
}

interface MathFieldInputProps {
  /** Applied once, when the field mounts (the dialog remounts it per opening) */
  initialLatex: string;
  onChange: (latex: string) => void;
}

/**
 * The MathLive <math-field>. Only ever rendered inside FormulaDialog through
 * next/dynamic, so the ~850 KB chunk is paid for on the first "Wstaw wzór".
 */
export function MathFieldInput({ initialLatex, onChange }: MathFieldInputProps) {
  const ref = useRef<MathfieldElement>(null);
  const onChangeRef = useRef(onChange);

  useEffect(() => {
    onChangeRef.current = onChange;
  }, [onChange]);

  useEffect(() => {
    const field = ref.current;
    if (!field) return;
    field.value = initialLatex;
    const handleInput = () => onChangeRef.current(field.value);
    field.addEventListener("input", handleInput);
    // Deferred: the dialog's focus trap (a parent, so its effect runs after
    // this one) moves focus to the dialog container when it opens
    const focusFrame = requestAnimationFrame(() => field.focus());
    return () => {
      cancelAnimationFrame(focusFrame);
      field.removeEventListener("input", handleInput);
      // The virtual keyboard is a global panel; it must not outlive the dialog
      window.mathVirtualKeyboard?.hide();
    };
  }, [initialLatex]);

  return (
    <math-field
      ref={ref}
      math-virtual-keyboard-policy="auto"
      aria-label="Wzór"
      style={{
        display: "block",
        width: "100%",
        fontSize: "1.6rem",
        padding: "12px",
        border: "1px solid #bdbdbd",
        borderRadius: 4,
      }}
    />
  );
}
