import type { Metadata } from "next";
import { PasswordResetRequest } from "@/components/auth/PasswordResetRequest";

export const metadata: Metadata = {
  title: "Nie pamiętam hasła",
  robots: { index: false, follow: false },
};

export default function PasswordResetRequestPage() {
  return <PasswordResetRequest />;
}
