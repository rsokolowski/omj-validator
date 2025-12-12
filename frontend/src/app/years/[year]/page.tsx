import Link from "next/link";
import { Box, Card, CardContent, Typography, Grid } from "@mui/material";
import { EmojiEvents, MilitaryTech, Stars } from "@mui/icons-material";
import { Breadcrumb } from "@/components/layout/Breadcrumb";
import { PageHeader } from "@/components/layout/PageHeader";
import { serverFetch } from "@/lib/api/server";
import { EtapsResponse } from "@/lib/types";
import { ETAP_NAMES } from "@/lib/utils/constants";

export const dynamic = "force-dynamic";

interface YearPageProps {
  params: Promise<{ year: string }>;
}

// Etap metadata with colors, icons, and descriptions
const ETAP_META: Record<
  string,
  {
    color: string;
    bgColor: string;
    borderColor: string;
    hoverBg: string;
    icon: React.ReactNode;
    description: string;
    difficulty: string;
  }
> = {
  etap1: {
    color: "#166534",
    bgColor: "#dcfce7",
    borderColor: "#86efac",
    hoverBg: "#bbf7d0",
    icon: <MilitaryTech sx={{ fontSize: 48, color: "#166534" }} />,
    description: "Eliminacje szkolne",
    difficulty: "★☆☆",
  },
  etap2: {
    color: "#9a3412",
    bgColor: "#ffedd5",
    borderColor: "#fdba74",
    hoverBg: "#fed7aa",
    icon: <EmojiEvents sx={{ fontSize: 48, color: "#ea580c" }} />,
    description: "Etap wojewódzki",
    difficulty: "★★☆",
  },
  etap3: {
    color: "#7c3aed",
    bgColor: "#f3e8ff",
    borderColor: "#c4b5fd",
    hoverBg: "#e9d5ff",
    icon: <Stars sx={{ fontSize: 48, color: "#7c3aed" }} />,
    description: "Finał ogólnopolski",
    difficulty: "★★★",
  },
};

async function getEtaps(year: string): Promise<EtapsResponse> {
  return serverFetch<EtapsResponse>(`/api/years/${year}`);
}

export default async function YearPage({ params }: YearPageProps) {
  const { year } = await params;
  const data = await getEtaps(year);

  const breadcrumbItems = [
    { label: "Lata", href: "/years" },
    { label: year },
  ];

  return (
    <Box>
      <PageHeader
        title={`OMJ ${year}`}
        subtitle="Wybierz etap zawodów - od eliminacji szkolnych do finału"
      >
        <Breadcrumb items={breadcrumbItems} />
      </PageHeader>

      <Grid container spacing={3}>
        {data.etaps.map((etap) => {
          const meta = ETAP_META[etap] || {
            color: "#374151",
            bgColor: "#f3f4f6",
            borderColor: "#d1d5db",
            hoverBg: "#e5e7eb",
            icon: null,
            description: "",
            difficulty: "",
          };

          return (
            <Grid key={etap} size={{ xs: 12, sm: 6, md: 4 }}>
              <Link
                href={`/years/${year}/${etap}`}
                style={{ textDecoration: "none" }}
                aria-label={ETAP_NAMES[etap] || etap}
              >
                <Card
                  sx={{
                    bgcolor: meta.bgColor,
                    border: "2px solid",
                    borderColor: meta.borderColor,
                    transition: "all 0.2s ease",
                    "&:hover": {
                      transform: "translateY(-4px)",
                      bgcolor: meta.hoverBg,
                      boxShadow: `0 12px 24px -8px ${meta.borderColor}`,
                    },
                  }}
                >
                  <CardContent sx={{ p: 3 }}>
                    {/* Icon */}
                    <Box
                      sx={{
                        display: "flex",
                        justifyContent: "center",
                        mb: 2,
                      }}
                    >
                      {meta.icon}
                    </Box>

                    {/* Title */}
                    <Typography
                      variant="h5"
                      sx={{
                        fontWeight: 700,
                        color: meta.color,
                        textAlign: "center",
                        mb: 0.5,
                      }}
                    >
                      {ETAP_NAMES[etap] || etap}
                    </Typography>

                    {/* Description */}
                    <Typography
                      sx={{
                        color: meta.color,
                        textAlign: "center",
                        fontSize: "0.9rem",
                        opacity: 0.8,
                        mb: 2,
                      }}
                    >
                      {meta.description}
                    </Typography>

                    {/* Difficulty indicator */}
                    <Typography
                      sx={{
                        textAlign: "center",
                        color: meta.color,
                        fontSize: "1.25rem",
                        letterSpacing: "2px",
                      }}
                    >
                      {meta.difficulty}
                    </Typography>
                  </CardContent>
                </Card>
              </Link>
            </Grid>
          );
        })}
      </Grid>

      {/* Info box */}
      <Box
        sx={{
          mt: 4,
          p: 3,
          bgcolor: "grey.50",
          borderRadius: 2,
          border: "1px solid",
          borderColor: "grey.200",
        }}
      >
        <Typography
          variant="body2"
          color="text.secondary"
          sx={{ textAlign: "center" }}
        >
          Każdy etap zawiera zadania o rosnącym poziomie trudności. Zalecamy
          rozpoczęcie od Etapu I.
        </Typography>
      </Box>
    </Box>
  );
}
