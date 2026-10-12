"use client";

import Link from "next/link";
import { Button, Stack } from "@mui/material";

const LINKS = [
  { href: "/admin/submissions", label: "Zgłoszenia" },
  { href: "/admin/settings", label: "Ustawienia AI" },
] as const;

/** Links between the admin pages; the current one is highlighted. */
export function AdminNav({ current }: { current: (typeof LINKS)[number]["href"] }) {
  return (
    <Stack direction="row" spacing={1} sx={{ mb: 2 }}>
      {LINKS.map((link) => (
        <Button
          key={link.href}
          component={Link}
          href={link.href}
          size="small"
          variant={link.href === current ? "contained" : "outlined"}
          aria-current={link.href === current ? "page" : undefined}
        >
          {link.label}
        </Button>
      ))}
    </Stack>
  );
}
