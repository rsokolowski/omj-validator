import Link from "next/link";
import { Box, Card, CardContent, Typography, Grid } from "@mui/material";
import { serverFetch } from "@/lib/api/client";
import { YearsResponse } from "@/lib/types";

export const dynamic = "force-dynamic";

async function getYears(): Promise<YearsResponse> {
  return serverFetch<YearsResponse>("/api/years");
}

export default async function YearsPage() {
  const data = await getYears();

  // Calculate edition number (OMJ started in 2019 as first edition)
  const getEdition = (year: string) => parseInt(year) - 2018;

  return (
    <Box>
      <Box sx={{ mb: 4 }}>
        <Typography variant="h4" component="h1" sx={{ fontWeight: 700, color: "grey.900", mb: 1 }}>
          Olimpiada Matematyczna Juniorów
        </Typography>
        <Typography color="text.secondary">
          Wybierz rok, aby zobaczyć zadania
        </Typography>
      </Box>

      <Grid container spacing={2}>
        {data.years.map((year) => (
          <Grid key={year} size={{ xs: 4, sm: 3, md: 2 }}>
            <Link href={`/years/${year}`} style={{ textDecoration: "none" }}>
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
                <CardContent sx={{ py: 3 }}>
                  <Typography
                    variant="h5"
                    sx={{ fontWeight: 700, color: "grey.900" }}
                  >
                    {year}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    {getEdition(year)}. edycja
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
