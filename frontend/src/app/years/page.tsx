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

  // Calculate edition number (OMG/OMJ started in 2005 as first edition)
  const toRoman = (num: number): string => {
    const romanNumerals: [number, string][] = [
      [1000, "M"], [900, "CM"], [500, "D"], [400, "CD"],
      [100, "C"], [90, "XC"], [50, "L"], [40, "XL"],
      [10, "X"], [9, "IX"], [5, "V"], [4, "IV"], [1, "I"]
    ];
    let result = "";
    for (const [value, symbol] of romanNumerals) {
      while (num >= value) {
        result += symbol;
        num -= value;
      }
    }
    return result;
  };
  const getEdition = (year: string) => toRoman(parseInt(year) - 2004);

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
