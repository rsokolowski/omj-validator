import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { Alert, Box, Button, Paper, Typography } from "@mui/material";
import { PageHeader } from "@/components/layout/PageHeader";
import { PrivateTaskCard } from "@/components/private-tasks/PrivateTaskCard";
import { APIError, serverFetch } from "@/lib/api/server";
import { PrivateTaskListResponse } from "@/lib/types";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Moje zadania",
  robots: { index: false, follow: false },
};

export default async function MyTasksPage() {
  let data: PrivateTaskListResponse;
  try {
    data = await serverFetch<PrivateTaskListResponse>("/api/private-tasks?limit=100");
  } catch (error) {
    if (error instanceof APIError && error.status === 401) {
      redirect("/login?next=/moje-zadania");
    }
    if (error instanceof APIError && error.status === 403) {
      return (
        <Box>
          <PageHeader title="Moje zadania" />
          <Alert severity="warning">
            Nie masz uprawnień do dodawania własnych zadań. Skontaktuj się z administratorem.
          </Alert>
        </Box>
      );
    }
    throw error;
  }

  return (
    <Box>
      <PageHeader
        title="Moje zadania"
        subtitle="Zadania spoza archiwum OMJ - z broszur, zbiorów i kartek. Widzisz je tylko Ty."
      />

      <Box sx={{ mb: 3 }}>
        <Button href="/moje-zadania/nowe" variant="contained">
          Dodaj zadanie
        </Button>
      </Box>

      {data.tasks.length === 0 ? (
        <Paper sx={{ p: 4, textAlign: "center" }}>
          <Typography sx={{ color: "grey.700", mb: 1 }}>Nie masz jeszcze żadnych własnych zadań.</Typography>
          <Typography variant="body2" sx={{ color: "grey.600" }}>
            Zrób zdjęcie zadania z broszury albo wpisz jego treść - AI oceni Twoje rozwiązanie
            tak jak zadania z OMJ.
          </Typography>
        </Paper>
      ) : (
        <Box
          component="section"
          aria-label="Lista moich zadań"
          sx={{ display: "grid", gap: 2, gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr", md: "1fr 1fr 1fr" } }}
        >
          {data.tasks.map((task) => (
            <PrivateTaskCard key={task.id} task={task} />
          ))}
        </Box>
      )}
      {data.has_more && (
        <Typography variant="body2" sx={{ color: "grey.600", mt: 2 }}>
          Pokazano {data.tasks.length} z {data.total_count} zadań.
        </Typography>
      )}
    </Box>
  );
}
