import { Box, Container, Typography, Link as MuiLink } from "@mui/material";
import { APP_NAME } from "@/lib/utils/constants";

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
            {APP_NAME} - Olimpiada Matematyczna Juniorów
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
            <MuiLink
              href="mailto:omj.validator@gmail.com"
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
