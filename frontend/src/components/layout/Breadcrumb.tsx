import Link from "next/link";
import { Breadcrumbs, Typography } from "@mui/material";
import NavigateNextIcon from "@mui/icons-material/NavigateNext";

interface BreadcrumbItem {
  label: string;
  href?: string;
}

interface BreadcrumbProps {
  items: BreadcrumbItem[];
}

export function Breadcrumb({ items }: BreadcrumbProps) {
  return (
    <Breadcrumbs
      separator={<NavigateNextIcon fontSize="small" sx={{ color: "grey.300" }} />}
      sx={{ mb: 3 }}
    >
      {items.map((item, index) => {
        const isLast = index === items.length - 1;

        if (isLast || !item.href) {
          return (
            <Typography
              key={index}
              sx={{
                color: isLast ? "grey.700" : "grey.500",
                fontWeight: isLast ? 500 : 400,
                fontSize: "0.875rem",
              }}
            >
              {item.label}
            </Typography>
          );
        }

        return (
          <Link
            key={index}
            href={item.href}
            style={{ textDecoration: "none" }}
          >
            <Typography
              sx={{
                color: "grey.500",
                fontSize: "0.875rem",
                "&:hover": {
                  color: "primary.main",
                },
              }}
            >
              {item.label}
            </Typography>
          </Link>
        );
      })}
    </Breadcrumbs>
  );
}
