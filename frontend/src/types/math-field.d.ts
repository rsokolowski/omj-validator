// <math-field> is MathLive's web component. React 19 renders custom elements
// natively; this tells TypeScript the tag exists and what it accepts.
import type { DetailedHTMLProps, HTMLAttributes } from "react";
import type { MathfieldElement } from "mathlive";

declare module "react" {
  namespace JSX {
    interface IntrinsicElements {
      "math-field": DetailedHTMLProps<HTMLAttributes<MathfieldElement>, MathfieldElement> & {
        "math-virtual-keyboard-policy"?: "auto" | "manual" | "sandboxed";
      };
    }
  }
}
