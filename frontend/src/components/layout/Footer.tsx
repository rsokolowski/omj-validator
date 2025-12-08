import { Box, Container, Typography, Link as MuiLink } from "@mui/material";

export function Footer() {
  return (
    <Box
      component="footer"
      sx={{
        bgcolor: "white",
        borderTop: "1px solid",
        borderColor: "grey.200",
        py: 3,
        mt: "auto",
      }}
    >
      <Container maxWidth="lg">
        <Box sx={{ textAlign: "center" }}>
          <Typography variant="body2" color="text.secondary">
            Olimpiada Matematyczna Juniorów - Walidator rozwiązań
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
            <MuiLink
              href="https://groups.google.com/g/omj-validator-alpha"
              target="_blank"
              rel="noopener noreferrer"
              sx={{ color: "primary.main" }}
            >
              Kontakt / Zgłoś błąd
            </MuiLink>
          </Typography>
        </Box>
      </Container>
    </Box>
  );
}
