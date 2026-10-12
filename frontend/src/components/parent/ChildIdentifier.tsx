"use client";

import { Box, Typography } from "@mui/material";
import type { ParentChild } from "@/lib/types";

/** "Login dziecka: kasia.b" - wyrozniony, zeby rodzic od razu wiedzial, o ktore konto chodzi. */
export function ChildIdentifier({ child }: { child: ParentChild }) {
  return (
    <Box sx={{ bgcolor: "grey.50", border: "1px solid", borderColor: "grey.200", borderRadius: 2, p: 2 }}>
      <Typography variant="body2" sx={{ color: "grey.600" }}>
        {child.identifier_label}
      </Typography>
      <Typography sx={{ fontWeight: 700, fontSize: "1.125rem", color: "grey.900", wordBreak: "break-all" }}>
        {child.identifier}
      </Typography>
    </Box>
  );
}
