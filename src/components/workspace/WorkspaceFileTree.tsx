// src/components/workspace/WorkspaceFileTree.tsx
// Slim sidebar listing all recordings. Highlights the currently-open document.
// Calls ensureDocumentForRecording for legacy recordings without a workspace_document.

import { useEffect, useCallback, useState } from "react";
import { useNavigate, useRouterState } from "@tanstack/react-router";
import { commands } from "@/lib/bindings";
import type { RecordingItem } from "@/lib/bindings";
import { formatDate } from "@/lib/format";
import { Mic } from "lucide-react";

export function WorkspaceFileTree() {
  const navigate = useNavigate();
  const routerState = useRouterState();
  const [recordings, setRecordings] = useState<RecordingItem[]>([]);
  const [loadingId, setLoadingId] = useState<string | null>(null);

  // Extract current documentId from route matches (works from any depth)
  const currentDocumentId: string | null =
    routerState.matches
      .map((m) => (m.params as Record<string, string>).documentId)
      .find(Boolean) ?? null;

  const load = useCallback(async () => {
    const result = await commands.listRecordings();
    if (result.status === "ok") setRecordings(result.data);
  }, []);

  useEffect(() => {
    load();
    const timer = setInterval(load, 5000);
    return () => clearInterval(timer);
  }, [load]);

  const handleClick = async (item: RecordingItem) => {
    if (loadingId) return;
    let docId = item.document_id;
    if (!docId) {
      setLoadingId(item.id);
      const result = await commands.ensureDocumentForRecording(item.id);
      setLoadingId(null);
      if (result.status !== "ok") return;
      docId = result.data;
      // Refresh list so document_id shows up
      load();
    }
    navigate({ to: "/workspace/$documentId", params: { documentId: docId } });
  };

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="shrink-0 px-3 py-2 flex items-center justify-between border-b border-border-default">
        <span className="text-xs font-semibold text-text-secondary uppercase tracking-wide">
          录音 ({recordings.length})
        </span>
      </div>

      {/* List */}
      <div className="flex-1 overflow-y-auto py-1">
        {recordings.length === 0 && (
          <div className="flex flex-col items-center justify-center h-32 gap-2 text-text-muted">
            <Mic className="w-6 h-6 opacity-30" />
            <p className="text-xs">暂无录音</p>
          </div>
        )}
        {recordings.map((item) => {
          const isActive = item.document_id === currentDocumentId && currentDocumentId !== null;
          const isLoading = loadingId === item.id;

          return (
            <button
              key={item.id}
              onClick={() => handleClick(item)}
              disabled={isLoading}
              className={[
                "w-full text-left px-3 py-2 transition-colors flex flex-col gap-0.5 min-w-0",
                isActive
                  ? "bg-accent-primary/15 text-accent-primary"
                  : "text-text-primary hover:bg-bg-tertiary",
                isLoading && "opacity-60 cursor-wait",
              ]
                .filter(Boolean)
                .join(" ")}
            >
              <span className="flex items-center gap-1.5 min-w-0">
                <Mic className="w-3 h-3 shrink-0" />
                <span className="truncate text-xs font-medium leading-tight">
                  {item.title}
                </span>
              </span>
              <span
                className={[
                  "text-xs ml-4.5 truncate",
                  isActive ? "text-accent-primary/70" : "text-text-muted",
                ].join(" ")}
              >
                {formatDate(item.created_at)}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
