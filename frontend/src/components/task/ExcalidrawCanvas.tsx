"use client";

import { useRef } from "react";
import { Box } from "@mui/material";
import { Excalidraw, MainMenu, exportToBlob } from "@excalidraw/excalidraw";
import type { AppState, ExcalidrawImperativeAPI } from "@excalidraw/excalidraw/types";
import "@excalidraw/excalidraw/index.css";

export interface DrawingHandle {
  isEmpty: () => boolean;
  /** PNG on a white background, like a photographed sheet of paper */
  toPng: () => Promise<Blob>;
}

interface ExcalidrawCanvasProps {
  onReady: (handle: DrawingHandle) => void;
  onEmptyChange: (empty: boolean) => void;
}

// Children use this, so everything that leads off the page is removed: the
// main menu's links (GitHub, Discord, X), the help dialog (docs, blog, YouTube),
// the library browser (libraries.excalidraw.com), web embeds and the Mermaid
// dialog (mermaid.js.org). Buttons without an API switch are hidden here; the
// dialogs they open are also closed in onChange, since shortcuts reach them too.
// UPGRADE NOTE: the selectors below target @excalidraw/excalidraw 0.18.1 class
// names and test ids. After bumping the package, run the e2e test "the drawing
// editor offers no way off the page" (e2e/tests/text-solutions.spec.ts) - it is
// the tripwire if a renamed class brings a hidden button back.
// !important: Excalidraw's own display rules are at least as specific and load later.
const hidden = { display: "none !important" };
const hideOffPageUi = {
  "& .default-sidebar-trigger, & .sidebar-trigger__label-element:has(.default-sidebar-trigger)": hidden,
  "& .help-icon": hidden,
  // "Osadź z sieci" and the Mermaid item share this test id; the unclassed
  // div is the "Generate" heading left empty without them
  '& .App-toolbar__extra-tools-dropdown [data-testid="toolbar-embeddable"]': hidden,
  "& .App-toolbar__extra-tools-dropdown .dropdown-menu-container > div:not([class])": hidden,
} as const;

function offPageDialogOpen(appState: AppState): boolean {
  const dialog = appState.openDialog?.name;
  return appState.openSidebar?.tab === "library" || dialog === "help" || dialog === "ttd";
}

/**
 * Only ever rendered inside DrawingDialog through next/dynamic. The parent
 * must give this element a height - Excalidraw fills its container.
 */
export function ExcalidrawCanvas({ onReady, onEmptyChange }: ExcalidrawCanvasProps) {
  const apiRef = useRef<ExcalidrawImperativeAPI | null>(null);

  const ready = (api: ExcalidrawImperativeAPI) => {
    apiRef.current = api;
    onReady({
      isEmpty: () => api.getSceneElements().length === 0,
      toPng: () =>
        exportToBlob({
          elements: api.getSceneElements(),
          appState: { exportBackground: true, viewBackgroundColor: "#ffffff" },
          files: api.getFiles(),
          mimeType: "image/png",
        }),
    });
  };

  return (
    <Box sx={{ height: "100%", minHeight: 320, ...hideOffPageUi }}>
      <Excalidraw
        langCode="pl-PL"
        excalidrawAPI={ready}
        aiEnabled={false}
        validateEmbeddable={false}
        UIOptions={{
          canvasActions: {
            loadScene: false,
            saveToActiveFile: false,
            export: false,
            saveAsImage: false,
          },
        }}
        onChange={(elements, appState) => {
          onEmptyChange(elements.filter((el) => !el.isDeleted).length === 0);
          if (offPageDialogOpen(appState)) {
            apiRef.current?.updateScene({ appState: { openSidebar: null, openDialog: null } });
          }
        }}
      >
        <MainMenu>
          <MainMenu.DefaultItems.ClearCanvas />
        </MainMenu>
      </Excalidraw>
    </Box>
  );
}
