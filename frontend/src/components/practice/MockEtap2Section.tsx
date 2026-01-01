"use client";

import { Box, Typography } from "@mui/material";
import { GraphNode } from "@/lib/types";
import { MOCK_ETAP2_SETS } from "@/lib/utils/constants";
import { MockEtap2SetCard } from "./MockEtap2SetCard";
import { PracticeTimer } from "./PracticeTimer";

interface MockEtap2SectionProps {
  nodes: GraphNode[];
}

export function MockEtap2Section({ nodes }: MockEtap2SectionProps) {
  // Create a map for quick lookup
  const nodeMap = new Map(nodes.map((n) => [n.key, n]));

  return (
    <Box>
      {/* Timer */}
      <PracticeTimer />

      {/* Info text */}
      <Typography variant="body2" sx={{ color: "grey.600", mb: 3 }}>
        Każdy zestaw zawiera 5 zadań o trudności typowej dla etapu 2.
        Maksymalna liczba punktów: 30 (6 punktów za zadanie).
      </Typography>

      {/* Mock sets */}
      <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
        {MOCK_ETAP2_SETS.map((set) => (
          <MockEtap2SetCard key={set.id} set={set} nodeMap={nodeMap} />
        ))}
      </Box>
    </Box>
  );
}
