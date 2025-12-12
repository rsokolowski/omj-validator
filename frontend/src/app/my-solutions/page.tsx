import { redirect } from "next/navigation";
import { Box, Paper, Alert, Typography } from "@mui/material";
import { serverFetch, APIError } from "@/lib/api/server";
import { MySolutionsDashboard } from "@/components/my-solutions/MySolutionsDashboard";
import { PageHeader } from "@/components/layout/PageHeader";

interface AuthResponse {
  user: { email: string; name: string } | null;
  is_authenticated: boolean;
}

type AuthStatusResult =
  | { type: "success"; data: AuthResponse }
  | { type: "auth_error" }
  | { type: "server_error"; message: string };

async function getAuthStatus(): Promise<AuthStatusResult> {
  try {
    const data = await serverFetch<AuthResponse>("/api/auth/me");
    return { type: "success", data };
  } catch (error) {
    if (error instanceof APIError && (error.status === 401 || error.status === 403)) {
      return { type: "auth_error" };
    }
    return { type: "server_error", message: error instanceof Error ? error.message : "Unknown error" };
  }
}

export default async function MySolutionsPage() {
  const result = await getAuthStatus();

  // Handle server errors
  if (result.type === "server_error") {
    return (
      <Box>
        <PageHeader title="Moje rozwiązania" />
        <Paper sx={{ p: 4, textAlign: "center" }}>
          <Alert severity="error" sx={{ mb: 2 }}>
            Nie udało się załadować strony
          </Alert>
          <Typography variant="body1" color="text.secondary">
            {result.message}
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
    redirect("/login?next=/my-solutions");
  }

  return (
    <Box>
      <PageHeader
        title="Moje rozwiązania"
        subtitle="Przeglądaj historię swoich rozwiązań i śledź postępy."
      />
      <MySolutionsDashboard />
    </Box>
  );
}
