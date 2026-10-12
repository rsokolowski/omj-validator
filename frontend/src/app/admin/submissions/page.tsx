import { Box } from "@mui/material";
import { AdminGate } from "@/components/admin/AdminGate";
import { AdminNav } from "@/components/admin/AdminNav";
import { AdminSubmissionsTable } from "@/components/admin/AdminSubmissionsTable";
import { PageHeader } from "@/components/layout/PageHeader";

export default function AdminSubmissionsPage() {
  return (
    <AdminGate loginNext="/admin/submissions">
      <Box>
        <PageHeader
          title="Panel administratora"
          subtitle="Przeglądaj i filtruj rozwiązania wszystkich użytkowników."
        >
          <AdminNav current="/admin/submissions" />
        </PageHeader>
        <AdminSubmissionsTable />
      </Box>
    </AdminGate>
  );
}
