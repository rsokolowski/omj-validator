import Link from "next/link";
import { Box, Card, CardContent, Typography, Grid } from "@mui/material";
import { Breadcrumb } from "@/components/layout/Breadcrumb";
import { serverFetch } from "@/lib/api/server";
import { EtapsResponse } from "@/lib/types";
import { ETAP_NAMES } from "@/lib/utils/constants";

export const dynamic = "force-dynamic";

interface YearPageProps {
  params: Promise<{ year: string }>;
}

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
      <Breadcrumb items={breadcrumbItems} />

      <Box sx={{ mb: 4 }}>
        <Typography variant="h4" component="h1" sx={{ fontWeight: 700, color: "grey.900", mb: 1 }}>
          {year}
        </Typography>
        <Typography color="text.secondary">
          Wybierz etap zawodów
        </Typography>
      </Box>

      <Grid container spacing={2}>
        {data.etaps.map((etap) => (
          <Grid key={etap} size={{ xs: 6, sm: 4, md: 3 }}>
            <Link href={`/years/${year}/${etap}`} style={{ textDecoration: "none" }}>
              <Card
                sx={{
                  textAlign: "center",
                  transition: "all 0.15s ease",
                  "&:hover": {
                    transform: "translateY(-2px)",
                    boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.1)",
                  },
                }}
              >
                <CardContent sx={{ py: 4 }}>
                  <Typography
                    variant="h6"
                    sx={{ fontWeight: 600, color: "grey.800" }}
                  >
                    {ETAP_NAMES[etap] || etap}
                  </Typography>
                </CardContent>
              </Card>
            </Link>
          </Grid>
        ))}
      </Grid>
    </Box>
  );
}
