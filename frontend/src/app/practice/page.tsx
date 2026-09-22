import type { Metadata } from "next";
import Link from "next/link";
import { Box, Card, CardContent, Chip, Typography } from "@mui/material";
import TimerIcon from "@mui/icons-material/Timer";
import { PageHeader } from "@/components/layout/PageHeader";
import {
  MockEtap,
  MOCK_ETAP_CONFIG,
  MOCK_ETAP_DURATION_LABELS,
} from "@/lib/utils/constants";

export const metadata: Metadata = {
  title: "Praktyka",
  description:
    "Symulacje konkursu OMJ: próbny Etap 1 (7 zadań, 100 minut) i próbny Etap 2 (5 zadań, 3 godziny) z odliczaniem czasu.",
  alternates: { canonical: "/practice" },
};

const ETAPS: MockEtap[] = ["etap1", "etap2"];

export default function PracticePage() {
  return (
    <Box>
      <PageHeader
        title="Praktyka"
        subtitle="Rozwiąż cały zestaw zadań w warunkach zbliżonych do prawdziwego konkursu"
      />

      <Box
        sx={{
          display: "grid",
          gridTemplateColumns: { xs: "1fr", sm: "repeat(2, 1fr)" },
          gap: 3,
        }}
      >
        {ETAPS.map((etap) => {
          const config = MOCK_ETAP_CONFIG[etap];
          const maxPoints = config.tasksPerSet * config.pointsPerTask;

          return (
            <Link
              key={etap}
              href={config.path}
              style={{ textDecoration: "none" }}
            >
              <Card
                elevation={0}
                sx={{
                  height: "100%",
                  border: "1px solid",
                  borderColor: "grey.200",
                  borderRadius: 3,
                  transition: "all 0.2s ease",
                  "&:hover": {
                    borderColor: "primary.main",
                    transform: "translateY(-4px)",
                    boxShadow: "0 12px 24px -8px rgba(37, 99, 235, 0.15)",
                  },
                }}
              >
                <CardContent sx={{ p: 4 }}>
                  <Box
                    sx={{
                      width: 56,
                      height: 56,
                      borderRadius: 2,
                      bgcolor: "#dbeafe",
                      color: "primary.main",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      mb: 2.5,
                    }}
                  >
                    <TimerIcon sx={{ fontSize: 32 }} />
                  </Box>

                  <Typography
                    variant="h6"
                    component="h2"
                    sx={{ fontWeight: 700, color: "grey.900", mb: 1 }}
                  >
                    {config.label}
                  </Typography>

                  <Typography sx={{ color: "grey.600", lineHeight: 1.7, mb: 2 }}>
                    {config.description}
                  </Typography>

                  <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1 }}>
                    <Chip
                      size="small"
                      label={`${config.tasksPerSet} zadań`}
                      sx={{ bgcolor: "grey.100", color: "grey.700" }}
                    />
                    <Chip
                      size="small"
                      label={MOCK_ETAP_DURATION_LABELS[etap]}
                      sx={{ bgcolor: "grey.100", color: "grey.700" }}
                    />
                    <Chip
                      size="small"
                      label={`${maxPoints} pkt`}
                      sx={{ bgcolor: "grey.100", color: "grey.700" }}
                    />
                  </Box>

                  <Typography
                    sx={{
                      color: "primary.main",
                      fontWeight: 600,
                      mt: 2.5,
                      fontSize: "0.9rem",
                    }}
                  >
                    Rozpocznij →
                  </Typography>
                </CardContent>
              </Card>
            </Link>
          );
        })}
      </Box>
    </Box>
  );
}
