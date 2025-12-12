import { Box, Stack } from "@mui/material";
import { Breadcrumb } from "@/components/layout/Breadcrumb";
import { PageHeader } from "@/components/layout/PageHeader";
import { TaskCard } from "@/components/task/TaskCard";
import { serverFetch } from "@/lib/api/server";
import { TasksResponse } from "@/lib/types";
import { ETAP_NAMES } from "@/lib/utils/constants";

export const dynamic = "force-dynamic";

interface EtapPageProps {
  params: Promise<{ year: string; etap: string }>;
}

async function getTasks(year: string, etap: string): Promise<TasksResponse> {
  return serverFetch<TasksResponse>(`/api/years/${year}/${etap}`);
}

export default async function EtapPage({ params }: EtapPageProps) {
  const { year, etap } = await params;
  const data = await getTasks(year, etap);

  const etapName = ETAP_NAMES[etap] || etap;
  const breadcrumbItems = [
    { label: "Lata", href: "/years" },
    { label: year, href: `/years/${year}` },
    { label: etapName },
  ];

  const taskCount = data.tasks.length;
  const taskWord = taskCount === 1 ? "zadanie" : taskCount < 5 ? "zadania" : "zadań";

  return (
    <Box>
      <PageHeader
        title={`${year} - ${etapName}`}
        subtitle={`${taskCount} ${taskWord}`}
      >
        <Breadcrumb items={breadcrumbItems} />
      </PageHeader>

      <Stack spacing={2}>
        {data.tasks.map((task) => (
          <TaskCard
            key={task.number}
            task={task}
            year={year}
            etap={etap}
            showStats={data.is_authenticated}
          />
        ))}
      </Stack>
    </Box>
  );
}
