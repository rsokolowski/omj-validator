import { Accordion, AccordionDetails, AccordionSummary, Box, Button, Typography } from "@mui/material";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import { MathContent } from "@/components/ui/MathContent";
import { ExerciseGroup } from "@/lib/types";
import { ExerciseList, solvedCount } from "./ExerciseList";

/** Moje zadania: one collapsed group of exercises per wzorzec. */
export function ExerciseGroups({ groups }: { groups: ExerciseGroup[] }) {
  if (groups.length === 0) return null;
  return (
    <Box component="section" aria-label="Ćwiczenia do wzorców" sx={{ mt: 4 }}>
      <Typography variant="h6" component="h2" sx={{ mb: 1 }}>
        Ćwiczenia do wzorców
      </Typography>
      {groups.map(({ pattern, exercises }) => (
        <Accordion key={pattern.id} disableGutters variant="outlined" sx={{ mb: 1 }}>
          <AccordionSummary expandIcon={<ExpandMoreIcon />} aria-controls={`cwiczenia-${pattern.id}`}>
            <Box sx={{ display: "flex", justifyContent: "space-between", width: "100%", gap: 2, pr: 1 }}>
              <Box sx={{ fontWeight: 500, "& .math-content": { display: "inline" } }}>
                Ćwiczenia: <MathContent content={pattern.trigger} />
              </Box>
              <Typography variant="body2" sx={{ color: "grey.600", whiteSpace: "nowrap" }}>
                {solvedCount(exercises)}/{exercises.length} rozwiązane
              </Typography>
            </Box>
          </AccordionSummary>
          <AccordionDetails id={`cwiczenia-${pattern.id}`}>
            <ExerciseList exercises={exercises} />
            <Box sx={{ display: "flex", gap: 1, mt: 2 }}>
              <Button size="small" variant="outlined" href={`/wzorce/${pattern.id}/cwiczenia/druk`}>
                Drukuj / PDF
              </Button>
              <Button size="small" href={`/wzorce/${pattern.id}`}>
                Do wzorca
              </Button>
            </Box>
          </AccordionDetails>
        </Accordion>
      ))}
    </Box>
  );
}
