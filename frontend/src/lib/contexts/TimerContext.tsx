"use client";

import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  ReactNode,
} from "react";
import { MockEtap, MOCK_ETAP_CONFIG } from "@/lib/utils/constants";

interface TimerState {
  etap: MockEtap | null; // etap the timer runs for; null when idle
  isRunning: boolean;
  isPaused: boolean;
  endTime: number | null; // Unix timestamp when timer ends (only when running)
  remainingMs: number;
}

interface TimerContextValue {
  /**
   * Etap the timer belongs to: running, paused or just expired.
   * null only when there is no timer at all (idle or after reset).
   */
  etap: MockEtap | null;
  /** Full duration of the timer that is set up, 0 when idle. */
  durationMs: number;
  isRunning: boolean;
  isPaused: boolean;
  remainingMs: number;
  isHydrated: boolean;
  startTimer: (etap: MockEtap) => void;
  pauseTimer: () => void;
  resumeTimer: () => void;
  resetTimer: () => void;
}

const TimerContext = createContext<TimerContextValue | null>(null);

const STORAGE_KEY = "omj-practice-timer";

const IDLE_STATE: TimerState = {
  etap: null,
  isRunning: false,
  isPaused: false,
  endTime: null,
  remainingMs: 0,
};

function isMockEtap(value: unknown): value is MockEtap {
  return value === "etap1" || value === "etap2";
}

export function TimerProvider({ children }: { children: ReactNode }) {
  const [isHydrated, setIsHydrated] = useState(false);
  const [state, setState] = useState<TimerState>(IDLE_STATE);

  // Load timer state from localStorage after hydration
  useEffect(() => {
    setIsHydrated(true);
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      try {
        const parsed = JSON.parse(stored) as Partial<TimerState>;
        // Payloads written before Próbny Etap 1 existed have no etap.
        const etap: MockEtap = isMockEtap(parsed.etap) ? parsed.etap : "etap2";
        if (parsed.isPaused && (parsed.remainingMs ?? 0) > 0) {
          // Restore paused state
          setState({
            etap,
            isRunning: false,
            isPaused: true,
            endTime: null,
            remainingMs: parsed.remainingMs as number,
          });
        } else if (parsed.isRunning && parsed.endTime) {
          const remaining = parsed.endTime - Date.now();
          if (remaining > 0) {
            setState({
              etap,
              isRunning: true,
              isPaused: false,
              endTime: parsed.endTime,
              remainingMs: remaining,
            });
          } else {
            // Timer expired
            localStorage.removeItem(STORAGE_KEY);
          }
        }
      } catch {
        localStorage.removeItem(STORAGE_KEY);
      }
    }
  }, []);

  // Update remaining time every second when running
  useEffect(() => {
    const endTime = state.endTime;
    if (!state.isRunning || !endTime) return;

    const interval = setInterval(() => {
      const remaining = endTime - Date.now();
      if (remaining <= 0) {
        setState((prev) => ({
          etap: prev.etap,
          isRunning: false,
          isPaused: false,
          endTime: null,
          remainingMs: 0,
        }));
        localStorage.removeItem(STORAGE_KEY);
      } else {
        setState((prev) => ({
          ...prev,
          remainingMs: remaining,
        }));
      }
    }, 1000);

    return () => clearInterval(interval);
  }, [state.isRunning, state.endTime]);

  const startTimer = useCallback((etap: MockEtap) => {
    const durationMs = MOCK_ETAP_CONFIG[etap].timerMs;
    const newState: TimerState = {
      etap,
      isRunning: true,
      isPaused: false,
      endTime: Date.now() + durationMs,
      remainingMs: durationMs,
    };
    setState(newState);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(newState));
  }, []);

  const pauseTimer = useCallback(() => {
    setState((prev) => {
      const newState: TimerState = {
        etap: prev.etap,
        isRunning: false,
        isPaused: true,
        endTime: null,
        remainingMs: prev.remainingMs,
      };
      localStorage.setItem(STORAGE_KEY, JSON.stringify(newState));
      return newState;
    });
  }, []);

  const resumeTimer = useCallback(() => {
    setState((prev) => {
      const newState: TimerState = {
        etap: prev.etap,
        isRunning: true,
        isPaused: false,
        endTime: Date.now() + prev.remainingMs,
        remainingMs: prev.remainingMs,
      };
      localStorage.setItem(STORAGE_KEY, JSON.stringify(newState));
      return newState;
    });
  }, []);

  const resetTimer = useCallback(() => {
    setState(IDLE_STATE);
    localStorage.removeItem(STORAGE_KEY);
  }, []);

  const durationMs = state.etap ? MOCK_ETAP_CONFIG[state.etap].timerMs : 0;

  return (
    <TimerContext.Provider
      value={{
        etap: state.etap,
        durationMs,
        isRunning: state.isRunning,
        isPaused: state.isPaused,
        remainingMs: state.remainingMs,
        isHydrated,
        startTimer,
        pauseTimer,
        resumeTimer,
        resetTimer,
      }}
    >
      {children}
    </TimerContext.Provider>
  );
}

export function useTimer() {
  const context = useContext(TimerContext);
  if (!context) {
    throw new Error("useTimer must be used within a TimerProvider");
  }
  return context;
}
