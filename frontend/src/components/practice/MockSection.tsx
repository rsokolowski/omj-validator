"use client";

import { Box, Typography } from "@mui/material";
import { GraphNode } from "@/lib/types";
import {
  MockEtap,
  MOCK_ETAP_CONFIG,
  MOCK_ETAP_DURATION_LABELS,
  MOCK_SETS,
} from "@/lib/utils/constants";
import { MockSetCard } from "./MockSetCard";
import { PracticeTimer } from "./PracticeTimer";

interface MockSectionProps {
  etap: MockEtap;
  nodes: GraphNode[];
}

export function MockSection({ etap, nodes }: MockSectionProps) {
  // Create a map for quick lookup
  const nodeMap = new Map(nodes.map((n) => [n.key, n]));

  const config = MOCK_ETAP_CONFIG[etap];
  const sets = MOCK_SETS[etap];
  const etapNumber = etap === "etap1" ? 1 : 2;
  const maxPoints = config.tasksPerSet * config.pointsPerTask;

  return (
    <Box>
      {/* Timer */}
      <PracticeTimer etap={etap} />

      {/* Info text */}
      <Typography variant="body2" sx={{ color: "grey.600", mb: 3 }}>
        Każdy zestaw zawiera {config.tasksPerSet} zadań o trudności typowej dla
        etapu {etapNumber}. Czas: {MOCK_ETAP_DURATION_LABELS[etap]}. Maksymalna
        liczba punktów: {maxPoints} ({config.pointsPerTask === 3 ? "3 punkty" : `${config.pointsPerTask} punktów`} za zadanie).
      </Typography>

      {/* Mock sets */}
      {sets.length === 0 ? (
        <Typography variant="body2" sx={{ color: "grey.500", fontStyle: "italic" }}>
          Zestawy są w przygotowaniu — zajrzyj tu wkrótce.
        </Typography>
      ) : (
        <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
          {sets.map((set) => (
            <MockSetCard key={set.id} set={set} etap={etap} nodeMap={nodeMap} />
          ))}
        </Box>
      )}
    </Box>
  );
}
