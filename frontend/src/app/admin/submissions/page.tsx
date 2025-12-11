import { redirect } from "next/navigation";
import { Container, Typography, Paper, Alert, Box } from "@mui/material";
import { serverFetch, APIError } from "@/lib/api/server";
import { AdminMeResponse } from "@/lib/types";
import { AdminSubmissionsTable } from "@/components/admin/AdminSubmissionsTable";

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
      <Container maxWidth="lg" sx={{ py: 4 }}>
        <Paper sx={{ p: 4, textAlign: "center" }}>
          <Alert severity="error" sx={{ mb: 2 }}>
            Server Error
          </Alert>
          <Typography variant="body1" color="text.secondary">
            Failed to load admin panel: {result.message}
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
            Please try again later or contact support if the problem persists.
          </Typography>
        </Paper>
      </Container>
    );
  }

  // Redirect to login if not authenticated
  if (result.type === "auth_error" || !result.data.is_authenticated) {
    redirect("/login?next=/admin/submissions");
  }

  // Show access denied if not admin
  if (!result.data.is_admin) {
    return (
      <Container maxWidth="lg" sx={{ py: 4 }}>
        <Paper sx={{ p: 4, textAlign: "center" }}>
          <Alert severity="error" sx={{ mb: 2 }}>
            Access Denied
          </Alert>
          <Typography variant="body1" color="text.secondary">
            You do not have permission to access the admin panel.
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
            Contact an administrator if you believe this is an error.
          </Typography>
        </Paper>
      </Container>
    );
  }

  return (
    <Container maxWidth="lg" sx={{ py: 4 }}>
      <Box sx={{ mb: 3 }}>
        <Typography variant="h4" component="h1" gutterBottom>
          Admin: Submissions
        </Typography>
        <Typography variant="body2" color="text.secondary">
          View and filter all submissions across all users.
        </Typography>
      </Box>

      <AdminSubmissionsTable />
    </Container>
  );
}
