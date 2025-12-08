"use client";

import { useState } from "react";
import { Paper, Typography, Box, Chip, Tooltip, Collapse, Button } from "@mui/material";
import { SkillInfo } from "@/lib/types";

interface SkillsSectionProps {
  skillsRequired: SkillInfo[];
  skillsGained: SkillInfo[];
}

export function SkillsSection({ skillsRequired, skillsGained }: SkillsSectionProps) {
  const [expanded, setExpanded] = useState(false);

  const totalSkills = skillsRequired.length + skillsGained.length;

  return (
    <Paper sx={{ p: 3, mb: 3 }}>
      <Box
        sx={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          cursor: "pointer",
        }}
        onClick={() => setExpanded(!expanded)}
      >
        <Typography variant="h6" sx={{ color: "grey.700" }}>
          Umiejętności ({totalSkills})
        </Typography>
        <Button size="small">
          {expanded ? "Zwiń" : "Rozwiń"}
        </Button>
      </Box>

      <Collapse in={expanded}>
        <Box sx={{ mt: 2, pt: 1.5, borderTop: 1, borderColor: "grey.200" }}>
          {skillsRequired.length > 0 && (
            <Box sx={{ mb: skillsGained.length > 0 ? 3 : 0 }}>
              <Typography variant="subtitle2" sx={{ color: "grey.600", mb: 1.5, fontWeight: 600 }}>
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
              <Typography variant="subtitle2" sx={{ color: "grey.600", mb: 1.5, fontWeight: 600 }}>
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
