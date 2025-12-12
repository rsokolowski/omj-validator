"use client";

import Link from "next/link";
import {
  AppBar,
  Toolbar,
  Typography,
  Box,
  Avatar,
  Chip,
  Button,
  Container,
} from "@mui/material";
import { useAuth } from "@/lib/hooks/useAuth";
import { APP_NAME } from "@/lib/utils/constants";

export function Header() {
  const { user, isAuthenticated, isGroupMember, isAdmin, isLoading } = useAuth();

  return (
    <AppBar
      position="sticky"
      sx={{
        bgcolor: "white",
        borderBottom: "1px solid",
        borderColor: "grey.200",
        boxShadow: "none",
      }}
    >
      <Container maxWidth="lg">
        <Toolbar disableGutters sx={{ justifyContent: "space-between" }}>
          {/* Logo */}
          <Link href="/" style={{ textDecoration: "none" }}>
            <Typography
              variant="h6"
              sx={{
                fontWeight: 700,
                color: "grey.900",
                "&:hover": { color: "primary.main" },
              }}
            >
              {APP_NAME}
            </Typography>
          </Link>

          {/* Navigation */}
          <Box sx={{ display: "flex", alignItems: "center", gap: 3 }}>
            <Link
              href="/years"
              style={{ textDecoration: "none", color: "#4b5563" }}
            >
              <Typography
                sx={{
                  fontWeight: 500,
                  "&:hover": { color: "primary.main" },
                }}
              >
                Zadania
              </Typography>
            </Link>
            <Link
              href="/progress"
              style={{ textDecoration: "none", color: "#4b5563" }}
            >
              <Typography
                sx={{
                  fontWeight: 500,
                  "&:hover": { color: "primary.main" },
                }}
              >
                Nauka
              </Typography>
            </Link>

            {/* My solutions link - only visible to authenticated users */}
            {isAuthenticated && (
              <Link
                href="/my-solutions"
                style={{ textDecoration: "none", color: "#4b5563" }}
              >
                <Typography
                  sx={{
                    fontWeight: 500,
                    "&:hover": { color: "primary.main" },
                  }}
                >
                  Moje rozwiązania
                </Typography>
              </Link>
            )}

            {/* Admin link - only visible to admins */}
            {isAdmin && (
              <Link
                href="/admin/submissions"
                style={{ textDecoration: "none", color: "#4b5563" }}
              >
                <Chip
                  label="Admin"
                  size="small"
                  sx={{
                    bgcolor: "#7c3aed",
                    color: "white",
                    fontWeight: 600,
                    "&:hover": { bgcolor: "#6d28d9" },
                    cursor: "pointer",
                  }}
                />
              </Link>
            )}

            {/* User info / Auth */}
            {!isLoading && (
              <>
                {isAuthenticated && user ? (
                  <Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
                    <Box
                      sx={{
                        display: "flex",
                        alignItems: "center",
                        gap: 1,
                        bgcolor: "grey.50",
                        borderRadius: "20px",
                        px: 1.5,
                        py: 0.5,
                      }}
                    >
                      {user.picture && (
                        <Avatar
                          src={user.picture}
                          alt={user.name}
                          sx={{ width: 28, height: 28 }}
                          slotProps={{ img: { referrerPolicy: "no-referrer" } }}
                        />
                      )}
                      <Typography
                        sx={{
                          fontSize: "0.875rem",
                          color: "grey.700",
                          maxWidth: 150,
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {user.name || user.email}
                      </Typography>
                      {!isGroupMember && (
                        <Chip
                          label="tylko odczyt"
                          size="small"
                          sx={{
                            height: 20,
                            fontSize: "0.6875rem",
                            bgcolor: "#ff9800",
                            color: "white",
                            fontWeight: 600,
                            textTransform: "uppercase",
                          }}
                        />
                      )}
                    </Box>
                    {/* Use regular anchor to avoid Next.js prefetch triggering logout */}
                    <a
                      href="/logout"
                      style={{ textDecoration: "none", color: "#9ca3af" }}
                    >
                      <Typography sx={{ fontSize: "0.875rem" }}>
                        Wyloguj
                      </Typography>
                    </a>
                  </Box>
                ) : (
                  <Link href="/login" style={{ textDecoration: "none" }}>
                    <Button variant="text" sx={{ color: "primary.main" }}>
                      Zaloguj
                    </Button>
                  </Link>
                )}
              </>
            )}
          </Box>
        </Toolbar>
      </Container>
    </AppBar>
  );
}
