"use client";

import { Box, Typography } from "@mui/material";
import { ReactNode } from "react";

// Shared style constants for consistent page headers
const PAGE_HEADER_STYLES = {
  container: { mb: 4 },
  title: {
    fontWeight: 700,
    color: "grey.900",
    mb: 1,
  },
} as const;

/**
 * Shared page header component for consistent styling across pages.
 *
 * Usage:
 * ```tsx
 * // Basic usage
 * <PageHeader
 *   title="Moje rozwiązania"
 *   subtitle="Przeglądaj historię swoich rozwiązań i śledź postępy."
 * />
 *
 * // With breadcrumb (renders above title)
 * <PageHeader title="OMJ 2024" subtitle="Wybierz etap">
 *   <Breadcrumb items={breadcrumbItems} />
 * </PageHeader>
 * ```
 */
interface PageHeaderProps {
  /** Main page title (h1) */
  title: string;
  /** Optional subtitle/description below the title */
  subtitle?: string;
  /** Optional content to render above the title (typically breadcrumbs) */
  children?: ReactNode;
}

export function PageHeader({ title, subtitle, children }: PageHeaderProps) {
  return (
    <Box sx={PAGE_HEADER_STYLES.container}>
      {children}
      <Typography
        variant="h4"
        component="h1"
        sx={PAGE_HEADER_STYLES.title}
      >
        {title}
      </Typography>
      {subtitle && (
        <Typography color="text.secondary">
          {subtitle}
        </Typography>
      )}
    </Box>
  );
}
