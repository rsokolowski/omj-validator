import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { Alert, Box } from "@mui/material";
import { Breadcrumb } from "@/components/layout/Breadcrumb";
import { PageHeader } from "@/components/layout/PageHeader";
import { NewPatternForm } from "@/components/patterns/NewPatternForm";
import { serverFetch } from "@/lib/api/server";
import { PatternInitialDraft, PatternSource, PrivateTaskDetailResponse, User } from "@/lib/types";
import { CATEGORY_NAMES, ETAP_NAMES, PATTERN_ACTION_MAX, PATTERN_EXAMPLE_MAX, PATTERN_TRIGGER_MAX } from "@/lib/utils/constants";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Nowy wzorzec",
  robots: { index: false, follow: false },
};

const TASK_KEY = /^(\d{4})_(etap[123])_(\d{1,2})$/;
const PRIVATE_ID = /^[A-Za-z0-9_-]{12}$/;

interface PageProps {
  searchParams: Promise<{ task?: string; private?: string; draft?: string }>;
}

function one(value: string | string[] | undefined): string | undefined {
  return typeof value === "string" ? value : undefined;
}

/** A suggestion handed over from a task page, clamped like the backend would. */
function parseDraft(raw: string | undefined): PatternInitialDraft | null {
  if (!raw) return null;
  try {
    const data = JSON.parse(raw);
    const text = (value: unknown, max: number) => (typeof value === "string" ? value.slice(0, max) : "");
    const draft = {
      trigger: text(data.trigger, PATTERN_TRIGGER_MAX),
      action: text(data.action, PATTERN_ACTION_MAX),
      example: text(data.example, PATTERN_EXAMPLE_MAX),
      category: typeof data.category === "string" && data.category in CATEGORY_NAMES ? data.category : null,
    };
    return draft.trigger && draft.action ? draft : null;
  } catch {
    return null;
  }
}

export default async function NewPatternPage({ searchParams }: PageProps) {
  const params = await searchParams;
  const auth = await serverFetch<{ user: User | null; is_authenticated: boolean }>("/api/auth/me");
  if (!auth.is_authenticated) {
    redirect("/login?next=/wzorce/nowy");
  }

  const taskKey = one(params.task);
  const privateId = one(params.private);
  let source: PatternSource | null = null;
  let sourceLabel: string | null = null;
  const match = taskKey ? TASK_KEY.exec(taskKey) : null;
  if (match) {
    source = { task_key: taskKey };
    sourceLabel = `${ETAP_NAMES[match[2]] ?? match[2]} ${match[1]}, zadanie ${Number(match[3])}`;
  } else if (privateId && PRIVATE_ID.test(privateId)) {
    try {
      const data = await serverFetch<PrivateTaskDetailResponse>(`/api/private-tasks/${privateId}`);
      source = { private_task_id: privateId };
      sourceLabel = `Moje zadania: ${data.task.title}`;
    } catch {
      source = null;
    }
  }

  return (
    <Box>
      <PageHeader title="Nowy wzorzec" subtitle="Kiedy w treści widzę… to warto spróbować…">
        <Breadcrumb items={[{ label: "Wzorce", href: "/wzorce" }, { label: "Nowy" }]} />
      </PageHeader>
      {auth.user && auth.user.is_group_member === false ? (
        <Alert severity="warning">Nie masz uprawnień do tej funkcji. Skontaktuj się z administratorem.</Alert>
      ) : (
        <NewPatternForm source={source} sourceLabel={sourceLabel} initialDraft={parseDraft(one(params.draft))} />
      )}
    </Box>
  );
}
