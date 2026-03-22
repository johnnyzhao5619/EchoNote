// src/components/workspace/AiPanel.tsx
// "✨ AI 工具" Popover button — wraps AiTaskBar in a floating panel.
// Task 5 will replace the panel internals with streaming preview + insert-at-cursor.

import * as Popover from "@radix-ui/react-popover";
import { Sparkles } from "lucide-react";
import { AiTaskBar } from "./AiTaskBar";

interface AiPanelProps {
  documentId: string;
}

export function AiPanel({ documentId }: AiPanelProps) {
  return (
    <Popover.Root>
      <Popover.Trigger asChild>
        <button
          className={[
            "flex items-center gap-1 px-2 py-1 rounded text-xs font-medium",
            "border border-border-default text-text-secondary",
            "hover:bg-bg-tertiary hover:text-text-primary transition-colors",
          ].join(" ")}
          title="AI 工具"
        >
          <Sparkles className="w-3.5 h-3.5" />
          AI 工具
        </button>
      </Popover.Trigger>

      <Popover.Portal>
        <Popover.Content
          side="bottom"
          align="end"
          sideOffset={6}
          className={[
            "z-50 w-80 rounded-lg border border-border-default bg-bg-primary shadow-xl p-4",
            "animate-in fade-in-0 zoom-in-95",
          ].join(" ")}
        >
          <AiTaskBar documentId={documentId} />
          <Popover.Arrow className="fill-border-default" />
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}
