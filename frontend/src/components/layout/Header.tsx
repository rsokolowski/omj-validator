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
        {/* WCAG 1.4.10 (Reflow): pasek musi sie zmiescic w 320 px CSS, wiec
            zawija sie zamiast wypychac strone w poziomie. */}
        <Toolbar
          disableGutters
          sx={{
            justifyContent: "space-between",
            flexWrap: "wrap",
            rowGap: 1,
            py: { xs: 1, sm: 0 },
          }}
        >
          {/* Logo - wyglada jak h6, ale naglowkiem nie jest: naglowek poziomu 6
              przed <h1> psul hierarchie dokumentu (WCAG 1.3.1). */}
          <Link href="/" style={{ textDecoration: "none" }}>
            <Typography
              variant="h6"
              component="span"
              sx={{
                display: "block",
                fontWeight: 700,
                color: "grey.900",
                "&:hover": { color: "primary.main" },
              }}
            >
              {APP_NAME}
            </Typography>
          </Link>

          {/* Navigation - punkt orientacyjny <nav> (WCAG 2.4.1) */}
          <Box
            component="nav"
            aria-label="Nawigacja główna"
            sx={{
              display: "flex",
              alignItems: "center",
              flexWrap: "wrap",
              rowGap: 1,
              gap: { xs: 1.5, sm: 3 },
              fontSize: { xs: "0.875rem", sm: "1rem" },
            }}
          >
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
            <Link
              href="/practice/etap2"
              style={{ textDecoration: "none", color: "#4b5563" }}
            >
              <Typography
                sx={{
                  fontWeight: 500,
                  "&:hover": { color: "primary.main" },
                }}
              >
                Praktyka
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
                    bgcolor: "accent.main",
                    color: "accent.contrastText",
                    fontWeight: 600,
                    "&:hover": { bgcolor: "accent.dark" },
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
                            // bialy na #ff9800 to bylo 2,16:1;
                            // warning.main (#b45309) daje 5,02:1 (WCAG 1.4.3)
                            bgcolor: "warning.main",
                            color: "white",
                            fontWeight: 600,
                            textTransform: "uppercase",
                          }}
                        />
                      )}
                    </Box>
                    {/* Use regular anchor to avoid Next.js prefetch triggering logout */}
                    {/* Kolor #9ca3af dawal 2,54:1; #4b5563 daje 7,56:1 (WCAG 1.4.3) */}
                    <a
                      href="/logout"
                      style={{ textDecoration: "none", color: "#4b5563" }}
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
