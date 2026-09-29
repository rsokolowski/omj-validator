import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { Alert, Box } from "@mui/material";
import { Breadcrumb } from "@/components/layout/Breadcrumb";
import { PageHeader } from "@/components/layout/PageHeader";
import { NewPrivateTaskForm } from "@/components/private-tasks/NewPrivateTaskForm";
import { serverFetch } from "@/lib/api/server";
import { User } from "@/lib/types";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Dodaj zadanie",
  robots: { index: false, follow: false },
};

export default async function NewTaskPage() {
  const auth = await serverFetch<{ user: User | null; is_authenticated: boolean }>("/api/auth/me");
  if (!auth.is_authenticated) {
    redirect("/login?next=/moje-zadania/nowe");
  }

  return (
    <Box>
      <PageHeader title="Dodaj zadanie" subtitle="Ze zdjęcia albo wpisane ręcznie.">
        <Breadcrumb items={[{ label: "Moje zadania", href: "/moje-zadania" }, { label: "Dodaj" }]} />
      </PageHeader>
      {auth.user && auth.user.is_group_member === false ? (
        <Alert severity="warning">
          Nie masz uprawnień do dodawania własnych zadań. Skontaktuj się z administratorem.
        </Alert>
      ) : (
        <NewPrivateTaskForm />
      )}
    </Box>
  );
}
