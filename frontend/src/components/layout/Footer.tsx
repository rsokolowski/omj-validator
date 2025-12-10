import { Box, Container, Typography, Link as MuiLink } from "@mui/material";
import Link from "next/link";
import { GitHub } from "@mui/icons-material";
import { APP_NAME, CONTACT_EMAIL } from "@/lib/utils/constants";

export function Footer() {
  return (
    <Box
      component="footer"
      sx={{
        bgcolor: "grey.50",
        borderTop: "1px solid",
        borderColor: "grey.200",
        py: 4,
        mt: "auto",
      }}
    >
      <Container maxWidth="lg">
        {/* AI Disclaimer - subtle version */}
        <Typography
          variant="caption"
          sx={{
            display: "block",
            textAlign: "center",
            color: "grey.500",
            mb: 3,
            fontSize: "0.75rem",
          }}
        >
          Uwaga: Treści zadań, wskazówki, powiązania i oceny są generowane przez
          AI i mogą zawierać błędy. Serwis ma charakter edukacyjny.
        </Typography>

        {/* Main Footer Content */}
        <Box
          sx={{
            display: "grid",
            gridTemplateColumns: { xs: "1fr", md: "repeat(3, 1fr)" },
            gap: 4,
            mb: 3,
          }}
        >
          {/* About */}
          <Box>
            <Typography
              variant="subtitle2"
              sx={{ fontWeight: 600, mb: 1.5, color: "grey.800" }}
            >
              O projekcie
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
              {APP_NAME} to niekomercyjny projekt edukacyjny pomagający w
              przygotowaniu do Olimpiady Matematycznej Juniorów.
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Autor:{" "}
              <MuiLink
                href="https://github.com/rsokolowski"
                target="_blank"
                rel="noopener"
                sx={{ color: "primary.main" }}
              >
                Rafał Sokołowski
              </MuiLink>
            </Typography>
          </Box>

          {/* Links */}
          <Box>
            <Typography
              variant="subtitle2"
              sx={{ fontWeight: 600, mb: 1.5, color: "grey.800" }}
            >
              Linki
            </Typography>
            <Box sx={{ display: "flex", flexDirection: "column", gap: 0.75 }}>
              <MuiLink
                href="https://omj.edu.pl"
                target="_blank"
                rel="noopener"
                sx={{ color: "text.secondary", fontSize: "0.875rem" }}
              >
                Oficjalna strona OMJ
              </MuiLink>
              <MuiLink
                href="https://github.com/rsokolowski/omj-validator"
                target="_blank"
                rel="noopener"
                sx={{
                  color: "text.secondary",
                  fontSize: "0.875rem",
                  display: "flex",
                  alignItems: "center",
                  gap: 0.5,
                }}
              >
                <GitHub sx={{ fontSize: 16 }} />
                Kod źródłowy (GitHub)
              </MuiLink>
              <Link href="/regulamin" style={{ textDecoration: "none" }}>
                <Typography
                  sx={{
                    color: "text.secondary",
                    fontSize: "0.875rem",
                    "&:hover": { color: "primary.main" },
                  }}
                >
                  Regulamin
                </Typography>
              </Link>
            </Box>
          </Box>

          {/* Contact */}
          <Box>
            <Typography
              variant="subtitle2"
              sx={{ fontWeight: 600, mb: 1.5, color: "grey.800" }}
            >
              Kontakt
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
              Masz pytania lub znalazłeś błąd?
            </Typography>
            <MuiLink
              href={`mailto:${CONTACT_EMAIL}`}
              sx={{ color: "primary.main", fontSize: "0.875rem" }}
            >
              {CONTACT_EMAIL}
            </MuiLink>
          </Box>
        </Box>

        {/* Bottom Bar */}
        <Box
          sx={{
            borderTop: "1px solid",
            borderColor: "grey.200",
            pt: 3,
            display: "flex",
            flexDirection: { xs: "column", sm: "row" },
            justifyContent: "space-between",
            alignItems: "center",
            gap: 1,
          }}
        >
          <Typography variant="body2" color="text.secondary">
            {APP_NAME} © {new Date().getFullYear()}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Licencja MIT • Open Source
          </Typography>
        </Box>
      </Container>
    </Box>
  );
}
