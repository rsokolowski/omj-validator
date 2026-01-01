"use client";

import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  ReactNode,
} from "react";
import { ETAP2_TIMER_DURATION_MS } from "@/lib/utils/constants";

interface TimerState {
  isRunning: boolean;
  isPaused: boolean;
  endTime: number | null; // Unix timestamp when timer ends (only when running)
  remainingMs: number;
}

interface TimerContextValue {
  isRunning: boolean;
  isPaused: boolean;
  remainingMs: number;
  isHydrated: boolean;
  startTimer: () => void;
  pauseTimer: () => void;
  resumeTimer: () => void;
  resetTimer: () => void;
}

const TimerContext = createContext<TimerContextValue | null>(null);

const STORAGE_KEY = "omj-practice-timer";

export function TimerProvider({ children }: { children: ReactNode }) {
  const [isHydrated, setIsHydrated] = useState(false);
  const [state, setState] = useState<TimerState>({
    isRunning: false,
    isPaused: false,
    endTime: null,
    remainingMs: ETAP2_TIMER_DURATION_MS,
  });

  // Load timer state from localStorage after hydration
  useEffect(() => {
    setIsHydrated(true);
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      try {
        const parsed = JSON.parse(stored) as TimerState;
        if (parsed.isPaused && parsed.remainingMs > 0) {
          // Restore paused state
          setState({
            isRunning: false,
            isPaused: true,
            endTime: null,
            remainingMs: parsed.remainingMs,
          });
        } else if (parsed.isRunning && parsed.endTime) {
          const remaining = parsed.endTime - Date.now();
          if (remaining > 0) {
            setState({
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
        setState({
          isRunning: false,
          isPaused: false,
          endTime: null,
          remainingMs: 0,
        });
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

  const startTimer = useCallback(() => {
    const endTime = Date.now() + ETAP2_TIMER_DURATION_MS;
    const newState: TimerState = {
      isRunning: true,
      isPaused: false,
      endTime,
      remainingMs: ETAP2_TIMER_DURATION_MS,
    };
    setState(newState);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(newState));
  }, []);

  const pauseTimer = useCallback(() => {
    setState((prev) => {
      const newState: TimerState = {
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
      const endTime = Date.now() + prev.remainingMs;
      const newState: TimerState = {
        isRunning: true,
        isPaused: false,
        endTime,
        remainingMs: prev.remainingMs,
      };
      localStorage.setItem(STORAGE_KEY, JSON.stringify(newState));
      return newState;
    });
  }, []);

  const resetTimer = useCallback(() => {
    setState({
      isRunning: false,
      isPaused: false,
      endTime: null,
      remainingMs: ETAP2_TIMER_DURATION_MS,
    });
    localStorage.removeItem(STORAGE_KEY);
  }, []);

  return (
    <TimerContext.Provider
      value={{
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
