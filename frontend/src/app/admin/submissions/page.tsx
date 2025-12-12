import { redirect } from "next/navigation";
import { Box, Paper, Alert, Typography } from "@mui/material";
import { serverFetch, APIError } from "@/lib/api/server";
import { AdminMeResponse } from "@/lib/types";
import { AdminSubmissionsTable } from "@/components/admin/AdminSubmissionsTable";
import { PageHeader } from "@/components/layout/PageHeader";

type AdminStatusResult =
  | { type: "success"; data: AdminMeResponse }
  | { type: "auth_error" }
  | { type: "server_error"; message: string };

async function getAdminStatus(): Promise<AdminStatusResult> {
  try {
    const data = await serverFetch<AdminMeResponse>("/api/admin/me");
    return { type: "success", data };
  } catch (error) {
    if (error instanceof APIError && (error.status === 401 || error.status === 403)) {
      return { type: "auth_error" };
    }
    return { type: "server_error", message: error instanceof Error ? error.message : "Unknown error" };
  }
}

export default async function AdminSubmissionsPage() {
  const result = await getAdminStatus();

  // Handle server errors (show error message instead of auth error)
  if (result.type === "server_error") {
    return (
      <Box>
        <PageHeader title="Panel administratora" />
        <Paper sx={{ p: 4, textAlign: "center" }}>
          <Alert severity="error" sx={{ mb: 2 }}>
            Błąd serwera
          </Alert>
          <Typography variant="body1" color="text.secondary">
            Nie udało się załadować panelu: {result.message}
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
            Spróbuj ponownie później.
          </Typography>
        </Paper>
      </Box>
    );
  }

  // Redirect to login if not authenticated
  if (result.type === "auth_error" || !result.data.is_authenticated) {
    redirect("/login?next=/admin/submissions");
  }

  // Show access denied if not admin
  if (!result.data.is_admin) {
    return (
      <Box>
        <PageHeader title="Panel administratora" />
        <Paper sx={{ p: 4, textAlign: "center" }}>
          <Alert severity="error" sx={{ mb: 2 }}>
            Brak dostępu
          </Alert>
          <Typography variant="body1" color="text.secondary">
            Nie masz uprawnień do panelu administracyjnego.
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
            Skontaktuj się z administratorem, jeśli uważasz, że to błąd.
          </Typography>
        </Paper>
      </Box>
    );
  }

  return (
    <Box>
      <PageHeader
        title="Panel administratora"
        subtitle="Przeglądaj i filtruj rozwiązania wszystkich użytkowników."
      />
      <AdminSubmissionsTable />
    </Box>
  );
}
