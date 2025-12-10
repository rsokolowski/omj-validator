"use client";

import Link from "next/link";
import {
  Box,
  Typography,
  Button,
  Card,
  CardContent,
  Paper,
  Chip,
} from "@mui/material";
import {
  CameraAlt,
  Psychology,
  CheckCircle,
  Lightbulb,
  AccountTree,
  EmojiEvents,
  TipsAndUpdates,
} from "@mui/icons-material";
import { DifficultyStars } from "@/components/ui/DifficultyStars";
import { CategoryBadge } from "@/components/ui/CategoryBadge";
import { APP_NAME } from "@/lib/utils/constants";

export default function LandingPage() {
  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 8 }}>
      {/* Hero Section */}
      <HeroSection />

      {/* Statistics Banner */}
      <StatsBanner />

      {/* How It Works */}
      <HowItWorksSection />

      {/* Key Features */}
      <FeaturesSection />

      {/* Sample Task Preview */}
      <SampleTaskSection />

      {/* Final CTA */}
      <FinalCTASection />
    </Box>
  );
}

function HeroSection() {
  return (
    <Box
      sx={{
        textAlign: "center",
        py: { xs: 4, md: 6 },
      }}
    >
      {/* Main Headline */}
      <Typography
        variant="h1"
        sx={{
          fontSize: { xs: "2rem", sm: "2.5rem", md: "3rem" },
          fontWeight: 800,
          color: "grey.900",
          mb: 2,
          lineHeight: 1.2,
        }}
      >
        Przygotuj się do
        <Box
          component="span"
          sx={{
            display: "block",
            color: "primary.main",
          }}
        >
          Olimpiady Matematycznej
        </Box>
      </Typography>

      {/* Subheadline */}
      <Typography
        sx={{
          fontSize: { xs: "1.125rem", md: "1.25rem" },
          color: "grey.600",
          maxWidth: 600,
          mx: "auto",
          mb: 4,
          lineHeight: 1.6,
        }}
      >
        Sprawdź swoje rozwiązania za pomocą sztucznej inteligencji.
        Otrzymaj natychmiastową informację zwrotną i ucz się na błędach.
      </Typography>

      {/* CTA Buttons */}
      <Box
        sx={{
          display: "flex",
          gap: 2,
          justifyContent: "center",
          flexWrap: "wrap",
        }}
      >
        <Link href="/years" style={{ textDecoration: "none" }}>
          <Button
            variant="contained"
            size="large"
            sx={{
              px: 4,
              py: 1.5,
              fontSize: "1rem",
              fontWeight: 600,
              borderRadius: 2,
              textTransform: "none",
              boxShadow: "0 4px 14px 0 rgba(37, 99, 235, 0.4)",
              "&:hover": {
                boxShadow: "0 6px 20px 0 rgba(37, 99, 235, 0.5)",
              },
            }}
          >
            Przeglądaj zadania
          </Button>
        </Link>
        <Link href="/progress" style={{ textDecoration: "none" }}>
          <Button
            variant="outlined"
            size="large"
            sx={{
              px: 4,
              py: 1.5,
              fontSize: "1rem",
              fontWeight: 600,
              borderRadius: 2,
              textTransform: "none",
              borderWidth: 2,
              "&:hover": {
                borderWidth: 2,
              },
            }}
          >
            Ścieżka nauki
          </Button>
        </Link>
      </Box>
    </Box>
  );
}

function StatsBanner() {
  const stats = [
    { value: "340+", label: "zadań" },
    { value: "20+", label: "lat archiwum" },
    { value: "6", label: "kategorii" },
    { value: "3", label: "etapy" },
  ];

  return (
    <Paper
      elevation={0}
      sx={{
        bgcolor: "grey.100",
        borderRadius: 3,
        py: 4,
        px: 3,
      }}
    >
      <Box
        sx={{
          display: "grid",
          gridTemplateColumns: {
            xs: "repeat(2, 1fr)",
            md: "repeat(4, 1fr)",
          },
          gap: 3,
          textAlign: "center",
        }}
      >
        {stats.map((stat) => (
          <Box key={stat.label}>
            <Typography
              sx={{
                fontSize: { xs: "2rem", md: "2.5rem" },
                fontWeight: 800,
                color: "primary.main",
                lineHeight: 1,
              }}
            >
              {stat.value}
            </Typography>
            <Typography
              sx={{
                fontSize: "0.875rem",
                color: "grey.600",
                fontWeight: 500,
                mt: 0.5,
              }}
            >
              {stat.label}
            </Typography>
          </Box>
        ))}
      </Box>
    </Paper>
  );
}

function HowItWorksSection() {
  const steps = [
    {
      icon: <CameraAlt sx={{ fontSize: 40 }} />,
      title: "1. Wybierz zadanie",
      description:
        "Przeglądaj archiwum ponad 340 zadań z wielu lat olimpiady. Filtruj po kategorii i poziomie trudności.",
    },
    {
      icon: <Psychology sx={{ fontSize: 40 }} />,
      title: "2. Wyślij rozwiązanie",
      description:
        "Zrób zdjęcie swojego ręcznego rozwiązania i prześlij je do analizy przez sztuczną inteligencję.",
    },
    {
      icon: <CheckCircle sx={{ fontSize: 40 }} />,
      title: "3. Otrzymaj feedback",
      description:
        "AI oceni Twoje rozwiązanie zgodnie z oficjalnymi kryteriami i wskaże błędy do poprawy.",
    },
  ];

  return (
    <Box>
      <Typography
        variant="h2"
        sx={{
          fontSize: { xs: "1.5rem", md: "2rem" },
          fontWeight: 700,
          textAlign: "center",
          mb: 1,
          color: "grey.900",
        }}
      >
        Jak to działa?
      </Typography>
      <Typography
        sx={{
          textAlign: "center",
          color: "grey.600",
          mb: 5,
          maxWidth: 500,
          mx: "auto",
        }}
      >
        Trzy proste kroki do lepszego przygotowania
      </Typography>

      <Box
        sx={{
          display: "grid",
          gridTemplateColumns: {
            xs: "1fr",
            md: "repeat(3, 1fr)",
          },
          gap: 4,
        }}
      >
        {steps.map((step) => (
          <Card
            key={step.title}
            elevation={0}
            sx={{
              textAlign: "center",
              border: "1px solid",
              borderColor: "grey.200",
              borderRadius: 3,
              transition: "all 0.2s ease",
              "&:hover": {
                borderColor: "primary.main",
                transform: "translateY(-4px)",
                boxShadow: "0 12px 24px -8px rgba(37, 99, 235, 0.15)",
              },
            }}
          >
            <CardContent sx={{ p: 4 }}>
              <Box
                sx={{
                  width: 80,
                  height: 80,
                  borderRadius: "50%",
                  bgcolor: "primary.main",
                  color: "white",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  mx: "auto",
                  mb: 3,
                }}
              >
                {step.icon}
              </Box>
              <Typography
                variant="h6"
                sx={{
                  fontWeight: 700,
                  mb: 1.5,
                  color: "grey.900",
                }}
              >
                {step.title}
              </Typography>
              <Typography
                sx={{
                  color: "grey.600",
                  lineHeight: 1.7,
                }}
              >
                {step.description}
              </Typography>
            </CardContent>
          </Card>
        ))}
      </Box>
    </Box>
  );
}

function FeaturesSection() {
  const features = [
    {
      icon: <Psychology sx={{ fontSize: 32 }} />,
      title: "Ocena AI",
      description:
        "Sztuczna inteligencja analizuje Twoje rozwiązanie i porównuje z oficjalnymi kryteriami punktacji OMJ.",
      color: "#2563eb",
      bgColor: "#dbeafe",
    },
    {
      icon: <Lightbulb sx={{ fontSize: 32 }} />,
      title: "Progresywne wskazówki",
      description:
        "4 poziomy podpowiedzi - od ogólnego zrozumienia do konkretnej wskazówki. Nie psuj sobie zabawy!",
      color: "#d97706",
      bgColor: "#fef3c7",
    },
    {
      icon: <AccountTree sx={{ fontSize: 32 }} />,
      title: "Ścieżka nauki",
      description:
        "Interaktywny graf zależności między zadaniami. Zobacz, które umiejętności musisz opanować.",
      color: "#059669",
      bgColor: "#dcfce7",
    },
    {
      icon: <EmojiEvents sx={{ fontSize: 32 }} />,
      title: "Oficjalna punktacja",
      description:
        "Oceny zgodne z systemem OMJ: 0, 2, 5 lub 6 punktów. Przygotuj się jak na prawdziwą olimpiadę.",
      color: "#7c3aed",
      bgColor: "#f3e8ff",
    },
  ];

  return (
    <Box>
      <Typography
        variant="h2"
        sx={{
          fontSize: { xs: "1.5rem", md: "2rem" },
          fontWeight: 700,
          textAlign: "center",
          mb: 1,
          color: "grey.900",
        }}
      >
        Dlaczego {APP_NAME}?
      </Typography>
      <Typography
        sx={{
          textAlign: "center",
          color: "grey.600",
          mb: 5,
          maxWidth: 500,
          mx: "auto",
        }}
      >
        Narzędzia stworzone z myślą o uczniach
      </Typography>

      <Box
        sx={{
          display: "grid",
          gridTemplateColumns: {
            xs: "1fr",
            sm: "repeat(2, 1fr)",
          },
          gap: 3,
        }}
      >
        {features.map((feature) => (
          <Card
            key={feature.title}
            elevation={0}
            sx={{
              border: "1px solid",
              borderColor: "grey.200",
              borderRadius: 3,
              transition: "all 0.2s ease",
              "&:hover": {
                transform: "translateY(-2px)",
                boxShadow: "0 8px 16px -4px rgba(0, 0, 0, 0.1)",
              },
            }}
          >
            <CardContent sx={{ p: 3 }}>
              <Box sx={{ display: "flex", gap: 2.5 }}>
                <Box
                  sx={{
                    width: 56,
                    height: 56,
                    borderRadius: 2,
                    bgcolor: feature.bgColor,
                    color: feature.color,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    flexShrink: 0,
                  }}
                >
                  {feature.icon}
                </Box>
                <Box>
                  <Typography
                    variant="h6"
                    sx={{
                      fontWeight: 700,
                      mb: 0.5,
                      color: "grey.900",
                      fontSize: "1.1rem",
                    }}
                  >
                    {feature.title}
                  </Typography>
                  <Typography
                    sx={{
                      color: "grey.600",
                      lineHeight: 1.6,
                      fontSize: "0.9rem",
                    }}
                  >
                    {feature.description}
                  </Typography>
                </Box>
              </Box>
            </CardContent>
          </Card>
        ))}
      </Box>
    </Box>
  );
}

function SampleTaskSection() {
  // Sample task data to showcase the UI
  const sampleTask = {
    number: 5,
    title: "Znajdź wszystkie liczby naturalne n, dla których...",
    difficulty: 3,
    categories: ["teoria_liczb", "algebra"],
    hasHints: true,
  };

  return (
    <Box>
      <Typography
        variant="h2"
        sx={{
          fontSize: { xs: "1.5rem", md: "2rem" },
          fontWeight: 700,
          textAlign: "center",
          mb: 1,
          color: "grey.900",
        }}
      >
        Zobacz przykładowe zadanie
      </Typography>
      <Typography
        sx={{
          textAlign: "center",
          color: "grey.600",
          mb: 5,
          maxWidth: 500,
          mx: "auto",
        }}
      >
        Każde zadanie zawiera metadane pomagające w nauce
      </Typography>

      <Box sx={{ maxWidth: 500, mx: "auto" }}>
        <Card
          elevation={0}
          sx={{
            border: "2px solid",
            borderColor: "primary.main",
            borderRadius: 3,
            overflow: "visible",
            position: "relative",
          }}
        >
          {/* Preview badge */}
          <Chip
            label="Podgląd"
            size="small"
            sx={{
              position: "absolute",
              top: -12,
              right: 16,
              bgcolor: "primary.main",
              color: "white",
              fontWeight: 600,
            }}
          />

          <CardContent sx={{ p: 3 }}>
            {/* Task header */}
            <Box
              sx={{ display: "flex", justifyContent: "space-between", mb: 2 }}
            >
              <Typography
                sx={{
                  fontWeight: 700,
                  color: "primary.main",
                  fontSize: "1.1rem",
                }}
              >
                Zadanie {sampleTask.number}
              </Typography>
              <Chip
                label="2024 / Etap II"
                size="small"
                sx={{
                  bgcolor: "grey.100",
                  color: "grey.600",
                  fontWeight: 500,
                }}
              />
            </Box>

            {/* Task title */}
            <Typography
              sx={{
                color: "grey.700",
                mb: 2,
                lineHeight: 1.6,
              }}
            >
              {sampleTask.title}
            </Typography>

            {/* Metadata row */}
            <Box
              sx={{
                display: "flex",
                flexWrap: "wrap",
                gap: 1,
                alignItems: "center",
                mb: 2,
              }}
            >
              <DifficultyStars difficulty={sampleTask.difficulty} />
              {sampleTask.categories.map((cat) => (
                <CategoryBadge key={cat} category={cat} size="small" />
              ))}
            </Box>

            {/* Hints indicator */}
            <Box
              sx={{
                display: "flex",
                alignItems: "center",
                gap: 1,
                p: 2,
                bgcolor: "#fef3c7",
                borderRadius: 2,
                border: "1px solid",
                borderColor: "#fde68a",
              }}
            >
              <TipsAndUpdates sx={{ color: "warning.main", fontSize: 20 }} />
              <Typography sx={{ fontSize: "0.875rem", color: "grey.700" }}>
                <strong>4 poziomy wskazówek</strong> - od ogólnych do
                szczegółowych
              </Typography>
            </Box>
          </CardContent>
        </Card>

        {/* Feature callouts */}
        <Box
          sx={{
            display: "grid",
            gridTemplateColumns: "repeat(3, 1fr)",
            gap: 2,
            mt: 3,
          }}
        >
          {[
            { label: "Poziom trudności", icon: "★★★☆☆" },
            { label: "Kategorie", icon: "6 typów" },
            { label: "Wskazówki", icon: "4 poziomy" },
          ].map((item) => (
            <Box key={item.label} sx={{ textAlign: "center" }}>
              <Typography
                sx={{
                  fontWeight: 700,
                  color: "primary.main",
                  fontSize: "1.1rem",
                }}
              >
                {item.icon}
              </Typography>
              <Typography
                sx={{
                  fontSize: "0.75rem",
                  color: "grey.500",
                  mt: 0.5,
                }}
              >
                {item.label}
              </Typography>
            </Box>
          ))}
        </Box>
      </Box>
    </Box>
  );
}

function FinalCTASection() {
  return (
    <Paper
      elevation={0}
      sx={{
        background: "linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%)",
        borderRadius: 4,
        py: 6,
        px: 4,
        textAlign: "center",
        color: "white",
      }}
    >
      <Typography
        variant="h2"
        sx={{
          fontSize: { xs: "1.5rem", md: "2rem" },
          fontWeight: 700,
          mb: 2,
        }}
      >
        Zacznij ćwiczyć już dziś!
      </Typography>
      <Typography
        sx={{
          fontSize: "1.1rem",
          opacity: 0.9,
          maxWidth: 500,
          mx: "auto",
          mb: 4,
          lineHeight: 1.6,
        }}
      >
        Ponad 340 zadań z 20 lat Olimpiady Matematycznej Juniorów czeka na Ciebie.
        Bezpłatnie.
      </Typography>
      <Link href="/years" style={{ textDecoration: "none" }}>
        <Button
          variant="contained"
          size="large"
          sx={{
            bgcolor: "white",
            color: "primary.main",
            px: 5,
            py: 1.5,
            fontSize: "1.1rem",
            fontWeight: 700,
            borderRadius: 2,
            textTransform: "none",
            "&:hover": {
              bgcolor: "grey.100",
            },
          }}
        >
          Przeglądaj zadania
        </Button>
      </Link>
    </Paper>
  );
}
