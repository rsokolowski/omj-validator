"use client";

import { Excalidraw, exportToBlob } from "@excalidraw/excalidraw";
import type { ExcalidrawImperativeAPI } from "@excalidraw/excalidraw/types";
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

/**
 * Only ever rendered inside DrawingDialog through next/dynamic. The parent
 * must give this element a height - Excalidraw fills its container.
 */
export function ExcalidrawCanvas({ onReady, onEmptyChange }: ExcalidrawCanvasProps) {
  const ready = (api: ExcalidrawImperativeAPI) => {
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
    <div style={{ height: "100%", minHeight: 320 }}>
      <Excalidraw
        langCode="pl-PL"
        excalidrawAPI={ready}
        onChange={(elements) => onEmptyChange(elements.filter((el) => !el.isDeleted).length === 0)}
      />
    </div>
  );
}
