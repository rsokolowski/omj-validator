"use client";

import { createContext, useCallback, useContext, useMemo, useState } from "react";

interface HintsUsage {
  /** Highest hint number revealed on this page visit */
  used: number;
  report: (revealed: number) => void;
}

const HintsUsageContext = createContext<HintsUsage | null>(null);

/**
 * Shares how many OMJ hints the student opened (HintsSection) with the submit
 * form, which records it with the submission. OMJ hints live only in the browser.
 */
export function HintsUsageProvider({ children }: { children: React.ReactNode }) {
  const [used, setUsed] = useState(0);
  const report = useCallback((revealed: number) => setUsed((current) => Math.max(current, revealed)), []);
  const value = useMemo(() => ({ used, report }), [used, report]);
  return <HintsUsageContext.Provider value={value}>{children}</HintsUsageContext.Provider>;
}

export function useHintsUsage(): HintsUsage | null {
  return useContext(HintsUsageContext);
}
