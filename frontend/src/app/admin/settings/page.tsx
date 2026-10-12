import { Box } from "@mui/material";
import { AdminGate } from "@/components/admin/AdminGate";
import { AdminNav } from "@/components/admin/AdminNav";
import { AiConfigForm } from "@/components/admin/AiConfigForm";
import { PageHeader } from "@/components/layout/PageHeader";

export default function AdminSettingsPage() {
  return (
    <AdminGate loginNext="/admin/settings">
      <Box>
        <PageHeader
          title="Ustawienia AI"
          subtitle="Dostawca i model używane do oceniania rozwiązań, wskazówek i wzorców. Zmiana dotyczy nowych wywołań."
        >
          <AdminNav current="/admin/settings" />
        </PageHeader>
        <AiConfigForm />
      </Box>
    </AdminGate>
  );
}
