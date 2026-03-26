// src/routes/workspace.index.tsx
// Default child when no document is selected — Obsidian-style empty state.

import { createFileRoute } from "@tanstack/react-router";
import { Mic } from "lucide-react";

export const Route = createFileRoute("/workspace/")({
  component: WorkspaceIndex,
});

function WorkspaceIndex() {
  return (
    <div className="flex flex-col h-full bg-bg-primary items-center justify-center gap-3 text-text-muted select-none">
      <Mic className="w-12 h-12 opacity-15" />
      <div className="text-center">
        <p className="text-sm font-medium">从左侧选择录音</p>
        <p className="text-xs mt-1 opacity-70">
          所有录音和转写内容都在这里管理
        </p>
      </div>
    </div>
  );
}
