"use client";

import { useState } from "react";
import { Paper, Typography, Box, Chip, Tooltip, Collapse, Button } from "@mui/material";
import { SkillInfo } from "@/lib/types";

interface SkillsSectionProps {
  skillsRequired: SkillInfo[];
  skillsGained: SkillInfo[];
}

const PANEL_ID = "umiejetnosci-panel";

export function SkillsSection({ skillsRequired, skillsGained }: SkillsSectionProps) {
  const [expanded, setExpanded] = useState(false);

  const totalSkills = skillsRequired.length + skillsGained.length;

  return (
    <Paper sx={{ p: 3, mb: 3 }}>
      {/* Sterowanie siedzi na samym przycisku, a nie na otaczającym <div>:
          div z onClick nie ma roli ani obsługi klawiatury (WCAG 2.1.1, 4.1.2).
          aria-expanded/aria-controls ogłaszają stan sekcji. */}
      <Box
        sx={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <Typography variant="h6" component="h2" sx={{ color: "grey.700" }}>
          Umiejętności ({totalSkills})
        </Typography>
        <Button
          size="small"
          onClick={() => setExpanded(!expanded)}
          aria-expanded={expanded}
          aria-controls={PANEL_ID}
        >
          {expanded ? "Zwiń" : "Rozwiń"} umiejętności
        </Button>
      </Box>

      <Collapse in={expanded}>
        <Box id={PANEL_ID} sx={{ mt: 2, pt: 1.5, borderTop: 1, borderColor: "grey.200" }}>
          {skillsRequired.length > 0 && (
            <Box sx={{ mb: skillsGained.length > 0 ? 3 : 0 }}>
              <Typography variant="subtitle2" component="h3" sx={{ color: "grey.600", mb: 1.5, fontWeight: 600 }}>
                Wymagane umiejętności:
              </Typography>
              <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1 }}>
                {skillsRequired.map((skill) => (
                  <Tooltip key={skill.id} title={skill.description} arrow>
                    <Chip
                      label={skill.name}
                      size="small"
                      sx={{
                        bgcolor: "#dbeafe",
                        color: "#1e40af",
                        border: "1px solid #93c5fd",
                        "&:hover": {
                          bgcolor: "#bfdbfe",
                        },
                      }}
                    />
                  </Tooltip>
                ))}
              </Box>
            </Box>
          )}

          {skillsGained.length > 0 && (
            <Box>
              <Typography variant="subtitle2" component="h3" sx={{ color: "grey.600", mb: 1.5, fontWeight: 600 }}>
                Zdobywane umiejętności:
              </Typography>
              <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1 }}>
                {skillsGained.map((skill) => (
                  <Tooltip key={skill.id} title={skill.description} arrow>
                    <Chip
                      label={skill.name}
                      size="small"
                      sx={{
                        bgcolor: "#dcfce7",
                        color: "#166534",
                        border: "1px solid #86efac",
                        "&:hover": {
                          bgcolor: "#bbf7d0",
                        },
                      }}
                    />
                  </Tooltip>
                ))}
              </Box>
            </Box>
          )}
        </Box>
      </Collapse>
    </Paper>
  );
}
