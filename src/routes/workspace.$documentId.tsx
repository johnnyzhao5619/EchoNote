// src/routes/workspace.$documentId.tsx
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useState, useCallback } from "react";
import { commands } from "@/lib/bindings";
import type { DocumentAsset, RecordingItem } from "@/lib/bindings";
import { useShellStore } from "@/store/shell";
import { formatDuration, formatDate } from "@/lib/format";
import { AiTaskBar } from "@/components/workspace/AiTaskBar";
import { Mic, Clock, ChevronDown, ChevronRight } from "lucide-react";

export const Route = createFileRoute("/workspace/$documentId")({
  component: DocumentPage,
});

// Role display metadata — single source of truth for ordering and labels
const ROLE_META: Record<string, { label: string; order: number }> = {
  transcript:    { label: "转写原文",  order: 0 },
  document_text: { label: "文档正文",  order: 1 },
  summary:       { label: "摘要",      order: 2 },
  meeting_brief: { label: "会议纪要",  order: 3 },
  translation:   { label: "翻译",      order: 4 },
  decisions:     { label: "决策",      order: 5 },
  action_items:  { label: "行动项",    order: 6 },
  next_steps:    { label: "下一步",    order: 7 },
};

/** Collapsible section for one text asset */
function AssetSection({ asset }: { asset: DocumentAsset }) {
  const [open, setOpen] = useState(true);
  const meta = ROLE_META[asset.role] ?? { label: asset.role, order: 99 };

  return (
    <section className="flex flex-col gap-2">
      <button
        className="flex items-center gap-1.5 text-xs font-semibold text-text-secondary uppercase tracking-wide hover:text-text-primary transition-colors"
        onClick={() => setOpen((v) => !v)}
      >
        {open ? (
          <ChevronDown className="w-3.5 h-3.5" />
        ) : (
          <ChevronRight className="w-3.5 h-3.5" />
        )}
        {meta.label}
      </button>
      {open && (
        <div className="text-sm text-text-primary leading-relaxed whitespace-pre-wrap rounded-md bg-bg-secondary border border-border-default p-3">
          {asset.content}
        </div>
      )}
    </section>
  );
}

/** Sidebar: list of recordings for navigation */
function WorkspaceSidebar({
  currentDocumentId,
}: {
  currentDocumentId: string;
}) {
  const navigate = useNavigate();
  const [recordings, setRecordings] = useState<RecordingItem[]>([]);

  useEffect(() => {
    commands.listRecordings().then((r) => {
      if (r.status === "ok") setRecordings(r.data);
    });
  }, []);

  return (
    <div className="flex flex-col h-full overflow-y-auto p-2 gap-1">
      <p className="px-2 py-1 text-xs font-semibold text-text-secondary uppercase tracking-wide">
        Recordings
      </p>
      {recordings.map((item) => (
        <button
          key={item.id}
          className={[
            "w-full text-left px-2 py-1.5 rounded text-sm truncate transition-colors",
            item.document_id === currentDocumentId
              ? "bg-accent-primary/15 text-accent-primary"
              : "text-text-primary hover:bg-bg-tertiary",
          ].join(" ")}
          onClick={() => {
            if (item.document_id && item.document_id !== currentDocumentId) {
              navigate({
                to: "/workspace/$documentId",
                params: { documentId: item.document_id },
              });
            }
          }}
        >
          {item.title}
        </button>
      ))}
    </div>
  );
}

function DocumentPage() {
  const { documentId } = Route.useParams();
  const { setSecondPanelContent } = useShellStore();
  const [assets, setAssets] = useState<DocumentAsset[]>([]);
  const [recording, setRecording] = useState<RecordingItem | null>(null);
  const [loading, setLoading] = useState(true);

  const sortAssets = useCallback((raw: DocumentAsset[]) =>
    [...raw].sort((a, b) => {
      const ao = ROLE_META[a.role]?.order ?? 99;
      const bo = ROLE_META[b.role]?.order ?? 99;
      return ao - bo;
    }), []);

  const loadData = useCallback(async () => {
    const [assetsResult, recordingsResult] = await Promise.all([
      commands.getDocumentAssets(documentId),
      commands.listRecordings(),
    ]);

    if (assetsResult.status === "ok") {
      setAssets(sortAssets(assetsResult.data));
    }

    if (recordingsResult.status === "ok") {
      const rec = recordingsResult.data.find((r) => r.document_id === documentId);
      setRecording(rec ?? null);
    }

    setLoading(false);
  }, [documentId, sortAssets]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Inject sidebar into SecondPanel; clean up on unmount
  useEffect(() => {
    setSecondPanelContent(
      <WorkspaceSidebar currentDocumentId={documentId} />
    );
    return () => setSecondPanelContent(null);
  }, [documentId, setSecondPanelContent]);

  // Poll for new assets after AI tasks complete
  useEffect(() => {
    const timer = setInterval(async () => {
      const result = await commands.getDocumentAssets(documentId);
      if (result.status === "ok") {
        setAssets(sortAssets(result.data));
      }
    }, 3000);
    return () => clearInterval(timer);
  }, [documentId, sortAssets]);

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center text-text-muted text-sm">
        Loading...
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full overflow-y-auto">
      {/* Document header */}
      <div className="shrink-0 px-6 py-4 border-b border-border-default">
        <div className="flex items-start gap-2">
          <Mic className="w-4 h-4 mt-0.5 shrink-0 text-accent-primary" />
          <div className="flex flex-col gap-0.5 min-w-0">
            <h1 className="text-base font-semibold text-text-primary truncate">
              {recording?.title ?? "Document"}
            </h1>
            <div className="flex items-center gap-3 text-xs text-text-muted">
              {recording && (
                <>
                  <span>{formatDate(recording.created_at)}</span>
                  <span className="flex items-center gap-1">
                    <Clock className="w-3 h-3" />
                    {formatDuration(recording.duration_ms)}
                  </span>
                </>
              )}
            </div>
          </div>
        </div>
        {/* AI task bar */}
        <div className="mt-3">
          <AiTaskBar documentId={documentId} />
        </div>
      </div>

      {/* Content sections */}
      <div className="flex-1 px-6 py-4 flex flex-col gap-5">
        {assets.length === 0 ? (
          <p className="text-sm text-text-muted">
            No content yet. Start recording and transcribing, or use AI tools above.
          </p>
        ) : (
          assets.map((asset) => (
            <AssetSection key={asset.id} asset={asset} />
          ))
        )}
      </div>
    </div>
  );
}
