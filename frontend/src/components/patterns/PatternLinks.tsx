"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  IconButton,
  MenuItem,
  Paper,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import { Check, Close, DeleteOutline } from "@mui/icons-material";
import { fetchAPI } from "@/lib/api/client";
import { patternsApi } from "@/lib/api/patterns";
import { PatternLink, PrivateTaskListResponse } from "@/lib/types";
import { ETAP_NAMES } from "@/lib/utils/constants";

interface PatternLinksProps {
  patternId: string;
  initialLinks: PatternLink[];
  /** Ask the AI for OMJ tasks right away (just after the pattern was saved) */
  autoSuggest?: boolean;
}

function LinkRow({ link, practiceHref, children }: {
  link: PatternLink;
  /** Task page that counts the solution as practice of this pattern */
  practiceHref?: string;
  children?: React.ReactNode;
}) {
  return (
    <Box sx={{ display: "flex", alignItems: "flex-start", gap: 1, py: 1, borderBottom: 1, borderColor: "grey.100" }}>
      <Box sx={{ flex: 1, minWidth: 0 }}>
        {link.available && link.url ? (
          <Link href={link.url} style={{ fontWeight: 600 }}>
            {link.label ? `${link.label} - ` : ""}
            {link.title}
          </Link>
        ) : (
          <Typography sx={{ color: "grey.500" }}>Zadanie niedostępne</Typography>
        )}
        {link.reason && (
          <Typography variant="body2" sx={{ color: "grey.700" }}>
            {link.reason}
          </Typography>
        )}
      </Box>
      {practiceHref && link.available && (
        <Button size="small" component={Link} href={practiceHref}>
          Rozwiąż
        </Button>
      )}
      {children}
    </Box>
  );
}

export function PatternLinks({ patternId, initialLinks, autoSuggest }: PatternLinksProps) {
  const [links, setLinks] = useState<PatternLink[]>(initialLinks);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [year, setYear] = useState("");
  const [etap, setEtap] = useState("etap1");
  const [number, setNumber] = useState("");
  const [privateTasks, setPrivateTasks] = useState<{ id: string; title: string }[] | null>(null);
  const [privateId, setPrivateId] = useState("");
  const suggested = useRef(false);
  const router = useRouter();
  const pathname = usePathname();

  const run = async (action: () => Promise<void>) => {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await action();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Wystąpił błąd.");
    } finally {
      setBusy(false);
    }
  };

  const suggest = () =>
    run(async () => {
      const { links: created } = await patternsApi.suggestLinks(patternId);
      setLinks((current) => [...current, ...created]);
      setNotice(created.length ? null : "AI nie znalazło nowych zadań do tego wzorca.");
    });

  useEffect(() => {
    if (autoSuggest && !suggested.current) {
      suggested.current = true;
      // Drop ?nowy=1 so a reload or "back" does not ask the AI again
      router.replace(pathname, { scroll: false });
      suggest();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoSuggest]);

  const setStatus = (link: PatternLink, status: "accepted" | "rejected") =>
    run(async () => {
      await patternsApi.setLinkStatus(patternId, link.id, status);
      setLinks((current) =>
        status === "rejected"
          ? current.filter((l) => l.id !== link.id)
          : current.map((l) => (l.id === link.id ? { ...l, status } : l))
      );
    });

  const remove = (link: PatternLink) =>
    run(async () => {
      await patternsApi.removeLink(patternId, link.id);
      setLinks((current) => current.filter((l) => l.id !== link.id));
    });

  const openAdd = () => {
    setAdding(true);
    if (privateTasks === null) {
      fetchAPI<PrivateTaskListResponse>("/api/private-tasks?limit=100")
        .then((data) => setPrivateTasks(data.tasks.map((t) => ({ id: t.id, title: t.title }))))
        .catch(() => setPrivateTasks([]));
    }
  };

  const add = () =>
    run(async () => {
      const source = privateId
        ? { private_task_id: privateId }
        : { task_key: `${year.trim()}_${etap}_${Number(number)}` };
      if (!privateId && (!/^\d{4}$/.test(year.trim()) || !Number(number))) {
        throw new Error("Podaj rok (np. 2024) i numer zadania.");
      }
      const { link } = await patternsApi.addLink(patternId, source);
      setLinks((current) => [...current, link]);
      setAdding(false);
      setYear("");
      setNumber("");
      setPrivateId("");
    });

  const source = links.filter((l) => l.role === "source");
  const accepted = links.filter((l) => l.role === "practice" && l.status === "accepted");
  const proposals = links.filter((l) => l.status === "suggested");

  return (
    <Paper sx={{ p: 3 }} component="section" aria-label="Zadania do tego wzorca">
      <Typography variant="h6" component="h2" sx={{ mb: 2 }}>
        Zadania do tego wzorca
      </Typography>

      {source.length > 0 && (
        <Box sx={{ mb: 2 }}>
          <Typography variant="subtitle2" sx={{ color: "grey.600" }}>
            Źródło
          </Typography>
          {source.map((link) => (
            <LinkRow key={link.id} link={link} practiceHref={`${link.url}?wzorzec=${patternId}`} />
          ))}
        </Box>
      )}

      <Box sx={{ mb: 2 }}>
        <Typography variant="subtitle2" sx={{ color: "grey.600" }}>
          Do ćwiczeń
        </Typography>
        {accepted.length === 0 && (
          <Typography variant="body2" sx={{ color: "grey.600", py: 1 }}>
            Jeszcze brak. Poproś AI o propozycje albo dodaj zadanie samodzielnie.
          </Typography>
        )}
        {accepted.map((link) => (
          <LinkRow key={link.id} link={link} practiceHref={`${link.url}?wzorzec=${patternId}`}>
            <Tooltip title="Usuń z listy">
              <IconButton aria-label="Usuń zadanie z listy" size="small" onClick={() => remove(link)} disabled={busy}>
                <DeleteOutline fontSize="small" />
              </IconButton>
            </Tooltip>
          </LinkRow>
        ))}
      </Box>

      {proposals.length > 0 && (
        <Box sx={{ mb: 2 }} data-testid="link-proposals">
          <Typography variant="subtitle2" sx={{ color: "grey.600" }}>
            Propozycje AI <Chip size="small" label={proposals.length} sx={{ ml: 0.5 }} />
          </Typography>
          {proposals.map((link) => (
            <LinkRow key={link.id} link={link}>
              <Tooltip title="Dodaj do ćwiczeń">
                <IconButton aria-label="Przyjmij propozycję" size="small" color="success"
                  onClick={() => setStatus(link, "accepted")} disabled={busy}>
                  <Check fontSize="small" />
                </IconButton>
              </Tooltip>
              <Tooltip title="Nie pasuje">
                <IconButton aria-label="Odrzuć propozycję" size="small" onClick={() => setStatus(link, "rejected")} disabled={busy}>
                  <Close fontSize="small" />
                </IconButton>
              </Tooltip>
            </LinkRow>
          ))}
        </Box>
      )}

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      {notice && <Alert severity="info" sx={{ mb: 2 }}>{notice}</Alert>}

      {adding && (
        <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap", alignItems: "center", mb: 2 }}>
          <TextField size="small" label="Rok" value={year} onChange={(e) => setYear(e.target.value)} sx={{ width: 90 }}
            disabled={busy || Boolean(privateId)} />
          <TextField size="small" select label="Etap" value={etap} onChange={(e) => setEtap(e.target.value)}
            sx={{ width: 140 }} disabled={busy || Boolean(privateId)}>
            {["etap1", "etap2", "etap3"].map((e) => (
              <MenuItem key={e} value={e}>{ETAP_NAMES[e] ?? e}</MenuItem>
            ))}
          </TextField>
          <TextField size="small" label="Nr" value={number} onChange={(e) => setNumber(e.target.value)} sx={{ width: 70 }}
            disabled={busy || Boolean(privateId)} />
          {privateTasks && privateTasks.length > 0 && (
            <TextField size="small" select label="albo moje zadanie" value={privateId}
              onChange={(e) => setPrivateId(e.target.value)} sx={{ minWidth: 200 }} disabled={busy}>
              <MenuItem value="">-</MenuItem>
              {privateTasks.map((t) => (
                <MenuItem key={t.id} value={t.id}>{t.title}</MenuItem>
              ))}
            </TextField>
          )}
          <Button onClick={add} disabled={busy} variant="contained" size="small">Dodaj</Button>
          <Button onClick={() => setAdding(false)} disabled={busy} size="small">Anuluj</Button>
        </Box>
      )}

      <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap" }}>
        <Button variant="outlined" onClick={suggest} disabled={busy}
          startIcon={busy ? <CircularProgress size={16} /> : null}>
          Znajdź więcej zadań
        </Button>
        {!adding && (
          <Button onClick={openAdd} disabled={busy}>
            Dodaj zadanie
          </Button>
        )}
      </Box>
    </Paper>
  );
}
