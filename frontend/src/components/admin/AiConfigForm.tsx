"use client";

import { useEffect, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  FormControl,
  FormControlLabel,
  FormHelperText,
  FormLabel,
  InputLabel,
  MenuItem,
  Paper,
  Radio,
  RadioGroup,
  Select,
  Stack,
  Typography,
} from "@mui/material";
import { APIError, getAiConfig, putAiConfig } from "@/lib/api/client";
import type {
  AiActiveModel,
  AiConfigResponse,
  AiFailoverStatus,
  AiProviderId,
  AiProviderOption,
} from "@/lib/types";

function errorText(error: unknown): string {
  if (error instanceof APIError || error instanceof Error) return error.message;
  return "Wystąpił błąd";
}

/** Why a provider cannot be selected, or null when it can. */
function unavailableReason(provider: AiProviderOption): string | null {
  if (!provider.configured) return "Brak klucza API";
  if (!provider.approved) return "Niezatwierdzony (RODO)";
  return null;
}

/**
 * The model to preselect for a provider: the active one if it belongs there,
 * nothing when the active (env) model is outside the catalog - so "Zapisz"
 * stays disabled until the admin picks one - else the provider's first model.
 */
function defaultModelFor(provider: AiProviderOption | undefined, active: AiActiveModel): string {
  if (!provider) return "";
  if (provider.id === active.provider) {
    return provider.models.some((m) => m.id === active.model) ? active.model : "";
  }
  return provider.models[0]?.id ?? "";
}

export function AiConfigForm() {
  const [config, setConfig] = useState<AiConfigResponse | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [provider, setProvider] = useState<AiProviderId | "">("");
  const [model, setModel] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [savedLabel, setSavedLabel] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getAiConfig()
      .then((data) => {
        if (cancelled) return;
        setConfig(data);
        setProvider(data.active.provider);
        setModel(defaultModelFor(data.providers.find((p) => p.id === data.active.provider), data.active));
      })
      .catch((error) => {
        if (!cancelled) setLoadError(errorText(error));
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (loadError) {
    return <Alert severity="error">Nie udało się wczytać ustawień AI: {loadError}</Alert>;
  }
  if (!config) {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", p: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  const { active, effective, fallback_reason: fallbackReason, providers } = config;
  const providerLabel = (id: string) => providers.find((p) => p.id === id)?.label ?? id;
  const fallingBack = effective.provider !== active.provider || effective.model !== active.model;
  const selectedProvider = providers.find((p) => p.id === provider);
  const selectedUsable = selectedProvider ? unavailableReason(selectedProvider) === null : false;
  const unchanged = provider === active.provider && model === active.model;
  const canSave = !saving && !unchanged && selectedUsable && model !== "";

  const handleProviderChange = (value: string) => {
    const next = providers.find((p) => p.id === value);
    if (!next) return;
    setProvider(next.id);
    setModel(defaultModelFor(next, active));
    setSaveError(null);
    setSavedLabel(null);
  };

  const handleSave = async () => {
    if (!selectedProvider) return;
    setSaving(true);
    setSaveError(null);
    setSavedLabel(null);
    try {
      const result = await putAiConfig(selectedProvider.id, model);
      setConfig({
        ...config,
        active: result.active,
        effective: result.effective,
        fallback_reason: result.fallback_reason,
        failover: result.failover,
      });
      setProvider(result.active.provider);
      setModel(result.active.model);
      setSavedLabel(`${result.active.model_label} (${providerLabel(result.active.provider)})`);
    } catch (error) {
      setSaveError(errorText(error));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Paper sx={{ p: 3 }}>
      <Stack spacing={3}>
        <Box>
          <Stack direction="row" spacing={1} sx={{ alignItems: "center", flexWrap: "wrap" }}>
            <Typography variant="h6" component="h2">
              Aktywny model: {active.model_label} ({providerLabel(active.provider)})
            </Typography>
            <Chip
              size="small"
              label={active.source === "db" ? "baza" : "konfiguracja serwera"}
              color={active.source === "db" ? "primary" : "default"}
              variant="outlined"
            />
          </Stack>
          {active.updated_at && (
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
              Zmienione {new Date(active.updated_at).toLocaleString("pl-PL")}
              {active.updated_by ? ` przez ${active.updated_by}` : ""}
            </Typography>
          )}
          {fallingBack && (
            <Alert severity="warning" sx={{ mt: 2 }}>
              Zapisany model jest niedostępny ({fallbackReason ?? "nieznany powód"}) — oceny wykonuje{" "}
              {effective.model_label} ({providerLabel(effective.provider)}).
            </Alert>
          )}
        </Box>

        <FormControl component="fieldset" disabled={saving}>
          <FormLabel component="legend">Dostawca</FormLabel>
          <RadioGroup value={provider} onChange={(e) => handleProviderChange(e.target.value)}>
            {providers.map((p) => {
              const reason = unavailableReason(p);
              return (
                <Box key={p.id}>
                  <FormControlLabel
                    value={p.id}
                    control={<Radio />}
                    label={p.label}
                    disabled={reason !== null}
                  />
                  {reason && <FormHelperText sx={{ mt: -1, ml: 4 }}>{reason}</FormHelperText>}
                </Box>
              );
            })}
          </RadioGroup>
        </FormControl>

        <FormControl fullWidth disabled={saving || !selectedUsable}>
          <InputLabel id="ai-model-label">Model</InputLabel>
          <Select
            labelId="ai-model-label"
            label="Model"
            value={model}
            onChange={(e) => {
              setModel(e.target.value);
              setSaveError(null);
              setSavedLabel(null);
            }}
          >
            {(selectedProvider?.models ?? []).map((m) => (
              <MenuItem key={m.id} value={m.id}>
                {m.label}
              </MenuItem>
            ))}
          </Select>
        </FormControl>

        <Stack direction="row" spacing={2} sx={{ alignItems: "center" }}>
          <Button variant="contained" onClick={handleSave} disabled={!canSave}>
            Zapisz
          </Button>
          {saving && (
            <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
              <CircularProgress size={20} />
              <Typography variant="body2" color="text.secondary">
                Sprawdzam model…
              </Typography>
            </Stack>
          )}
        </Stack>

        {config.failover && <FailoverStatus failover={config.failover} providerLabel={providerLabel} />}

        {savedLabel && (
          <Alert severity="success">Zapisano. Nowe oceny będą wykonywane modelem {savedLabel}.</Alert>
        )}
        {saveError && <Alert severity="error">{saveError}</Alert>}
      </Stack>
    </Paper>
  );
}

/** Read-only failover state: backup model, GDPR gate, circuit breaker (configured in the server env). */
function FailoverStatus({
  failover,
  providerLabel,
}: {
  failover: AiFailoverStatus;
  providerLabel: (id: string) => string;
}) {
  const { breaker } = failover;
  const breakerOpen = breaker.state === "open";
  const backup = `${failover.model_label}${failover.provider ? ` (${providerLabel(failover.provider)})` : ""}`;
  return (
    <Box component="section" aria-label="Zapasowy model">
      <Stack direction="row" spacing={1} sx={{ alignItems: "center", flexWrap: "wrap", mb: 1 }}>
        <Typography variant="subtitle1" component="h3">
          Zapasowy model: {backup}
        </Typography>
        <Chip
          size="small"
          label={failover.active ? "aktywny" : "nieaktywny"}
          color={failover.active ? "success" : "default"}
          variant="outlined"
        />
        <Chip
          size="small"
          label={failover.gate_open ? "RODO: zatwierdzony" : "RODO: niezatwierdzony"}
          color={failover.gate_open ? "success" : "warning"}
          variant="outlined"
        />
      </Stack>
      <Typography variant="body2" color="text.secondary">
        Gdy aktywny dostawca nie odpowiada (klucz, limit, awaria serwera, brak połączenia), wywołanie
        jest powtarzane raz na modelu zapasowym. Nigdy po zablokowaniu treści przez filtr
        bezpieczeństwa; przekroczony czas i błąd 500 tylko liczą się do bezpiecznika. Ustawienia:
        AI_FAILOVER_ENABLED, AI_FAILOVER_MODEL.
      </Typography>
      {!failover.active && failover.inactive_reason && (
        <Typography variant="body2" sx={{ mt: 0.5 }}>
          Nie działa: {failover.inactive_reason}.
        </Typography>
      )}
      {failover.active && (
        <Alert severity={breakerOpen ? "warning" : "info"} sx={{ mt: 1 }}>
          {breakerOpen
            ? `Aktywny dostawca uznany za niedostępny${breaker.last_error ? ` (${breaker.last_error})` : ""} — wszystkie wywołania idą do modelu zapasowego${
                breaker.open_until ? ` do ${new Date(breaker.open_until).toLocaleTimeString("pl-PL")}` : ""
              }.`
            : `Bezpiecznik zamknięty — wywołania idą do aktywnego modelu${
                breaker.consecutive_failures
                  ? ` (błędy z rzędu: ${breaker.consecutive_failures}/${failover.breaker_threshold}${
                      breaker.last_error ? `, ostatni: ${breaker.last_error}` : ""
                    })`
                  : ""
              }. Otwiera się od razu po błędzie klucza/modelu albo po ${failover.breaker_threshold} przejściowych błędach z rzędu, na ${failover.breaker_minutes} min.`}
        </Alert>
      )}
    </Box>
  );
}
