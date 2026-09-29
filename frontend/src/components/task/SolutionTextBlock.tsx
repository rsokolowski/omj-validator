"use client";

import { useId, useState, type MouseEvent } from "react";
import { Box, Button, Collapse } from "@mui/material";
import ExpandLessIcon from "@mui/icons-material/ExpandLess";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import { MathContent } from "@/components/ui/MathContent";
import { countChars, formatCount } from "@/lib/utils/solutionText";

interface SolutionTextBlockProps {
  text: string;
}

/**
 * A typed solution in a history view: collapsed by default (it can be long),
 * rendered with MathContent like the feedback. Used wherever a submission is
 * shown - task page, "Moje rozwiązania", admin table.
 */
export function SolutionTextBlock({ text }: SolutionTextBlockProps) {
  const [open, setOpen] = useState(false);
  const panelId = useId();

  const toggle = (e: MouseEvent<HTMLButtonElement>) => {
    // Some cards toggle themselves on click - this button must not
    e.stopPropagation();
    setOpen((current) => !current);
  };

  return (
    <Box sx={{ mt: 2 }}>
      <Button
        size="small"
        onClick={toggle}
        aria-expanded={open}
        aria-controls={panelId}
        startIcon={open ? <ExpandLessIcon /> : <ExpandMoreIcon />}
        sx={{ textTransform: "none", color: "grey.700" }}
      >
        Wpisany tekst rozwiązania ({formatCount(countChars(text))} znaków)
      </Button>
      <Collapse in={open}>
        <Box
          id={panelId}
          sx={{
            mt: 1,
            p: 2,
            bgcolor: "background.paper",
            border: 1,
            borderColor: "grey.200",
            borderRadius: 1,
            overflowWrap: "anywhere",
            color: "grey.800",
          }}
        >
          <MathContent content={text} />
        </Box>
      </Collapse>
    </Box>
  );
}
