import { Paper, Typography, Button } from "@mui/material";

interface LoginPromptProps {
  title?: string;
  message?: string;
  redirectUrl?: string;
}

export function LoginPrompt({
  title = "Polecane zadania",
  message = "Zaloguj się, aby zobaczyć spersonalizowane rekomendacje zadań",
  redirectUrl,
}: LoginPromptProps) {
  const loginHref = redirectUrl
    ? `/login?next=${encodeURIComponent(redirectUrl)}`
    : "/login";

  return (
    <Paper sx={{ p: 3, mb: 3, textAlign: "center" }}>
      <Typography variant="h6" sx={{ color: "grey.700", mb: 1 }}>
        {title}
      </Typography>
      <Typography variant="body2" sx={{ color: "grey.600", mb: 3 }}>
        {message}
      </Typography>
      <Button
        variant="contained"
        href={loginHref}
        sx={{ py: 1, px: 3 }}
      >
        Zaloguj się
      </Button>
    </Paper>
  );
}
