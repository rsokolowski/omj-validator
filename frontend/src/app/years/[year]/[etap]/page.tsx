import { Box, Typography, Stack } from "@mui/material";
import { Breadcrumb } from "@/components/layout/Breadcrumb";
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

  return (
    <Box>
      <Breadcrumb items={breadcrumbItems} />

      <Box sx={{ mb: 4 }}>
        <Typography variant="h4" component="h1" sx={{ fontWeight: 700, color: "grey.900", mb: 1 }}>
          {year} - {etapName}
        </Typography>
        <Typography color="text.secondary">
          {data.tasks.length} {data.tasks.length === 1 ? "zadanie" : data.tasks.length < 5 ? "zadania" : "zadań"}
        </Typography>
      </Box>

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
