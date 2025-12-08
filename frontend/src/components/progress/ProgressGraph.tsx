"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Box, Typography, CircularProgress } from "@mui/material";
import { GraphNode, GraphEdge } from "@/lib/types";
import cytoscape from "cytoscape";

interface ProgressGraphProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export function ProgressGraph({ nodes, edges }: ProgressGraphProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<cytoscape.Core | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!containerRef.current || nodes.length === 0) {
      setLoading(false);
      return;
    }

    // Status colors
    const getNodeColor = (status: string) => {
      switch (status) {
        case "mastered":
          return "#22c55e";
        case "unlocked":
          return "#3b82f6";
        case "locked":
        default:
          return "#9ca3af";
      }
    };

    // Prepare cytoscape elements
    const elements: cytoscape.ElementDefinition[] = [
      ...nodes.map((node) => ({
        data: {
          id: node.key,
          label: `${node.number}`,
          status: node.status,
          year: node.year,
          etap: node.etap,
          title: node.title,
          difficulty: node.difficulty,
        },
      })),
      ...edges.map((edge) => ({
        data: {
          id: `${edge.source}-${edge.target}`,
          source: edge.source,
          target: edge.target,
        },
      })),
    ];

    // Initialize Cytoscape
    cyRef.current = cytoscape({
      container: containerRef.current,
      elements,
      style: [
        {
          selector: "node",
          style: {
            label: "data(label)",
            "text-valign": "center",
            "text-halign": "center",
            "background-color": (ele: any) => getNodeColor(ele.data("status")),
            color: "#fff",
            "font-size": 12,
            "font-weight": "bold",
            width: 40,
            height: 40,
            "border-width": 2,
            "border-color": "#fff",
          },
        },
        {
          selector: "edge",
          style: {
            width: 2,
            "line-color": "#d1d5db",
            "target-arrow-color": "#d1d5db",
            "target-arrow-shape": "triangle",
            "curve-style": "bezier",
            "arrow-scale": 0.8,
          },
        },
        {
          selector: "node:selected",
          style: {
            "border-color": "#1e40af",
            "border-width": 3,
          },
        },
      ],
      layout: {
        name: "cose",
        animate: false,
        nodeDimensionsIncludeLabels: true,
        idealEdgeLength: () => 100,
        nodeRepulsion: () => 4500,
        padding: 50,
      },
      minZoom: 0.3,
      maxZoom: 2,
    });

    // Handle node clicks - navigate to task
    cyRef.current.on("tap", "node", (evt) => {
      const node = evt.target;
      const year = node.data("year");
      const etap = node.data("etap");
      const number = node.data("label");
      window.location.href = `/task/${year}/${etap}/${number}`;
    });

    setLoading(false);

    // Cleanup
    return () => {
      if (cyRef.current) {
        cyRef.current.destroy();
      }
    };
  }, [nodes, edges]);

  if (nodes.length === 0) {
    return (
      <Box sx={{ textAlign: "center", py: 4 }}>
        <Typography variant="body1" sx={{ color: "grey.500" }}>
          Brak zadań do wyświetlenia
        </Typography>
      </Box>
    );
  }

  return (
    <Box sx={{ position: "relative" }}>
      {loading && (
        <Box
          sx={{
            position: "absolute",
            top: "50%",
            left: "50%",
            transform: "translate(-50%, -50%)",
            zIndex: 1,
          }}
        >
          <CircularProgress />
        </Box>
      )}
      <Box
        ref={containerRef}
        sx={{
          width: "100%",
          height: 500,
          border: 1,
          borderColor: "grey.200",
          borderRadius: 1,
          bgcolor: "#fafafa",
        }}
      />
      <Typography variant="caption" sx={{ display: "block", mt: 1, color: "grey.500", textAlign: "center" }}>
        Kliknij na zadanie, aby przejść do jego szczegółów. Możesz przybliżać i przesuwać graf.
      </Typography>
    </Box>
  );
}
