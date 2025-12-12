import { redirect } from "next/navigation";
import { Container, Typography, Paper, Alert, Box } from "@mui/material";
import { serverFetch, APIError } from "@/lib/api/server";
import { MySolutionsDashboard } from "@/components/my-solutions/MySolutionsDashboard";

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
      <Container maxWidth="lg" sx={{ py: 4 }}>
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
      </Container>
    );
  }

  // Redirect to login if not authenticated
  if (result.type === "auth_error" || !result.data.is_authenticated) {
    redirect("/login?next=/my-solutions");
  }

  return (
    <Container maxWidth="lg" sx={{ py: 4 }}>
      <Box sx={{ mb: 3 }}>
        <Typography variant="h4" component="h1" gutterBottom>
          Moje rozwiązania
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Przeglądaj historię swoich rozwiązań i śledź postępy.
        </Typography>
      </Box>

      <MySolutionsDashboard />
    </Container>
  );
}
