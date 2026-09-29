"use client";

import { Component, type ReactNode } from "react";
import { Alert } from "@mui/material";

interface Props {
  children: ReactNode;
}

interface State {
  failed: boolean;
}

/**
 * A lazily loaded editor chunk (MathLive, Excalidraw) that fails to load must
 * not take the whole submit form with it: the dialog shows this message and the
 * student can cancel and still send photos or plain text.
 */
export class EditorLoadBoundary extends Component<Props, State> {
  state: State = { failed: false };

  static getDerivedStateFromError(): State {
    return { failed: true };
  }

  render() {
    if (this.state.failed) {
      return <Alert severity="error">Nie udało się wczytać edytora — spróbuj ponownie</Alert>;
    }
    return this.props.children;
  }
}
