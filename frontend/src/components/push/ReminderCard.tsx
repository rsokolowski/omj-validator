"use client";

import { useCallback, useEffect, useState } from "react";
import { Alert, Box, Button, CircularProgress, Paper, TextField, Typography } from "@mui/material";
import { pushApi, PushConfig } from "@/lib/api/push";

type Device = "loading" | "ios-install" | "unsupported" | "denied" | "off" | "on";

const SW_URL = "/sw.js";

function isIOS(): boolean {
  const ua = navigator.userAgent;
  // iPadOS reports itself as a Mac with a touch screen
  return /iPad|iPhone|iPod/.test(ua) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
}

function isInstalled(): boolean {
  return (
    window.matchMedia("(display-mode: standalone)").matches ||
    (navigator as Navigator & { standalone?: boolean }).standalone === true
  );
}

function pushSupported(): boolean {
  return "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
}

function keyBytes(base64url: string): Uint8Array<ArrayBuffer> {
  const base64 = (base64url + "=".repeat((4 - (base64url.length % 4)) % 4)).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(base64);
  const bytes = new Uint8Array(new ArrayBuffer(raw.length));
  for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);
  return bytes;
}

function sameKey(subscription: PushSubscription, publicKey: string): boolean {
  const current = subscription.options?.applicationServerKey;
  if (!current) return true; // Not exposed by every browser - assume it matches
  const a = new Uint8Array(current);
  const b = keyBytes(publicKey);
  return a.length === b.length && a.every((v, i) => v === b[i]);
}

async function currentSubscription(): Promise<PushSubscription | null> {
  const registration = await navigator.serviceWorker.getRegistration("/");
  return (await registration?.pushManager.getSubscription()) ?? null;
}

/** "Przypomnienia na telefonie": turn reminders about due wzorce on/off on this device. */
export function ReminderCard() {
  const [config, setConfig] = useState<PushConfig | null>(null);
  const [device, setDevice] = useState<Device>("loading");
  const [weekday, setWeekday] = useState("16:30");
  const [weekend, setWeekend] = useState("10:00");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const applyConfig = useCallback((next: PushConfig) => {
    setConfig(next);
    setWeekday(next.weekday_time);
    setWeekend(next.weekend_time);
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      let next: PushConfig;
      try {
        next = await pushApi.config();
      } catch {
        return; // Not signed in / no access - the card stays hidden
      }
      if (cancelled) return;
      applyConfig(next);
      if (!next.enabled || !next.public_key) return;
      if (!pushSupported()) {
        setDevice(isIOS() && !isInstalled() ? "ios-install" : "unsupported");
        return;
      }
      if (Notification.permission === "denied") {
        setDevice("denied");
        return;
      }
      try {
        const subscription = await currentSubscription();
        if (subscription && !sameKey(subscription, next.public_key)) {
          // The server's keys changed: this subscription can no longer be used
          await subscription.unsubscribe();
        } else if (subscription) {
          // Re-link the device to this account (and to the server, if it was forgotten)
          const synced = await pushApi.subscribe(subscription.toJSON());
          if (!cancelled) applyConfig(synced);
          if (!cancelled) setDevice("on");
          return;
        }
      } catch {
        // Fall through: offer to switch it on again
      }
      if (!cancelled) setDevice("off");
    })();
    return () => {
      cancelled = true;
    };
  }, [applyConfig]);

  const enable = async () => {
    if (!config?.public_key) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      // First, while the tap still counts as a user gesture (required on iPhone)
      const permission = await Notification.requestPermission();
      if (permission !== "granted") {
        setDevice(permission === "denied" ? "denied" : "off");
        return;
      }
      const registration = await navigator.serviceWorker.register(SW_URL, { scope: "/" });
      await navigator.serviceWorker.ready;
      const subscription = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: keyBytes(config.public_key),
      });
      applyConfig(await pushApi.subscribe(subscription.toJSON()));
      setDevice("on");
      setNotice("Przypomnienia są włączone na tym urządzeniu.");
    } catch (e) {
      setError(e instanceof Error && e.message ? e.message : "Nie udało się włączyć przypomnień.");
    } finally {
      setBusy(false);
    }
  };

  const disable = async () => {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const subscription = await currentSubscription();
      if (subscription) {
        const endpoint = subscription.endpoint;
        await subscription.unsubscribe();
        applyConfig(await pushApi.unsubscribe(endpoint));
      }
      setDevice("off");
    } catch (e) {
      setError(e instanceof Error && e.message ? e.message : "Nie udało się wyłączyć przypomnień.");
    } finally {
      setBusy(false);
    }
  };

  const saveTimes = async () => {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      applyConfig(await pushApi.saveTimes(weekday, weekend));
      setNotice("Zapisano godziny przypomnień.");
    } catch (e) {
      setError(e instanceof Error && e.message ? e.message : "Nie udało się zapisać godzin.");
    } finally {
      setBusy(false);
    }
  };

  const sendTest = async () => {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const { sent } = await pushApi.test();
      if (sent > 0) setNotice("Wysłano próbne powiadomienie - powinno pojawić się za chwilę.");
      else setError("Nie udało się dostarczyć powiadomienia. Wyłącz i włącz przypomnienia ponownie.");
    } catch (e) {
      setError(e instanceof Error && e.message ? e.message : "Nie udało się wysłać powiadomienia.");
    } finally {
      setBusy(false);
    }
  };

  if (!config?.enabled || device === "loading") return null;

  const timesChanged = weekday !== config.weekday_time || weekend !== config.weekend_time;

  return (
    <Paper sx={{ p: 3, mt: 3 }} component="section" aria-label="Przypomnienia na telefonie" data-testid="reminder-card">
      <Typography variant="h6" component="h2" sx={{ mb: 1 }}>
        Przypomnienia na telefonie
      </Typography>
      <Typography variant="body2" sx={{ color: "grey.700", mb: 2 }}>
        W dni, kiedy jakiś wzorzec czeka na powtórkę, telefon przypomni o tym raz dziennie. Stuknięcie w
        powiadomienie otwiera od razu powtórkę.
      </Typography>

      {device === "ios-install" && (
        <Alert severity="info" data-testid="reminder-ios-install">
          Na iPhonie przypomnienia działają tylko z aplikacji na ekranie początkowym. W Safari stuknij{" "}
          <strong>Udostępnij</strong>, potem <strong>Do ekranu początkowego</strong>, a następnie otwórz
          Trenera OMJ z nowej ikony i wróć tutaj (Wzorce).
        </Alert>
      )}
      {device === "unsupported" && (
        <Alert severity="info">Ta przeglądarka nie obsługuje powiadomień. Spróbuj w Chrome albo w Safari.</Alert>
      )}
      {device === "denied" && (
        <Alert severity="warning">
          Powiadomienia dla tej strony są zablokowane. Zezwól na nie w ustawieniach telefonu albo przeglądarki,
          a potem odśwież stronę.
        </Alert>
      )}

      {device === "off" && (
        <Button variant="contained" onClick={enable} disabled={busy} data-testid="reminder-enable">
          {busy ? <CircularProgress size={20} color="inherit" /> : "Włącz przypomnienia"}
        </Button>
      )}

      {device === "on" && (
        <Box>
          <Typography variant="body2" sx={{ mb: 2, fontWeight: 600 }} data-testid="reminder-on">
            Włączone na tym urządzeniu.
          </Typography>
          <Box sx={{ display: "flex", gap: 2, flexWrap: "wrap", alignItems: "center", mb: 2 }}>
            <TextField
              label="Dni szkolne (pn-pt)"
              type="time"
              size="small"
              value={weekday}
              onChange={(e) => setWeekday(e.target.value)}
              slotProps={{ inputLabel: { shrink: true }, htmlInput: { step: 300, min: "06:00", max: "21:00" } }}
            />
            <TextField
              label="Weekend (sb-nd)"
              type="time"
              size="small"
              value={weekend}
              onChange={(e) => setWeekend(e.target.value)}
              slotProps={{ inputLabel: { shrink: true }, htmlInput: { step: 300, min: "06:00", max: "21:00" } }}
            />
            {timesChanged && (
              <Button variant="contained" size="small" onClick={saveTimes} disabled={busy}>
                Zapisz godziny
              </Button>
            )}
          </Box>
          <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap" }}>
            <Button variant="outlined" size="small" onClick={sendTest} disabled={busy}>
              Wyślij próbne powiadomienie
            </Button>
            <Button size="small" color="inherit" onClick={disable} disabled={busy}>
              Wyłącz na tym urządzeniu
            </Button>
          </Box>
        </Box>
      )}

      {notice && (
        <Alert severity="success" sx={{ mt: 2 }}>
          {notice}
        </Alert>
      )}
      {error && (
        <Alert severity="error" sx={{ mt: 2 }}>
          {error}
        </Alert>
      )}
    </Paper>
  );
}
