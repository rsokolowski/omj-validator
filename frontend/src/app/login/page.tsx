import { Box } from "@mui/material";
import { LoginForm } from "@/components/auth/LoginForm";

export const dynamic = "force-dynamic";

interface LoginPageProps {
  searchParams: Promise<{ next?: string }>;
}

export default async function LoginPage({ searchParams }: LoginPageProps) {
  const { next } = await searchParams;
  const googleLoginUrl = next
    ? `/login/google?next=${encodeURIComponent(next)}`
    : "/login/google";

  return (
    <Box
      sx={{
        minHeight: "60vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      <LoginForm googleLoginUrl={googleLoginUrl} />
    </Box>
  );
}
