"use client";

import { Fragment } from "react";
import Link from "next/link";
import { Box, Chip } from "@mui/material";
import { MathContent } from "@/components/ui/MathContent";
import { splitTaskRefs, TaskRef } from "@/lib/utils/patternTasks";

/** An OMJ task named by the AI; opens in a new tab so the conversation stays. */
export function TaskChip({ task }: { task: TaskRef }) {
  return (
    <Chip
      size="small"
      variant="outlined"
      clickable
      component={Link}
      href={task.url}
      target="_blank"
      rel="noopener"
      label={task.label}
    />
  );
}

/** AI text with $LaTeX$; the OMJ tasks it names ([[2015_etap3_1]]) become links. */
export function TextWithTasks({ text }: { text: string }) {
  return (
    <Box component="span" sx={{ "& .math-content": { display: "inline" } }}>
      {splitTaskRefs(text).map((part, i) =>
        "task" in part ? (
          <Box key={i} component="span" sx={{ mx: 0.25 }}>
            <TaskChip task={part.task} />
          </Box>
        ) : (
          <Fragment key={i}>
            <MathContent content={part.text} />
          </Fragment>
        )
      )}
    </Box>
  );
}
