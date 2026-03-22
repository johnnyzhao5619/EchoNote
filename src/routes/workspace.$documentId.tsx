// src/routes/workspace.$documentId.tsx
import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState, useCallback } from "react";
import { useNavigate } from "@tanstack/react-router";
import { commands } from "@/lib/bindings";
import type { DocumentAsset, RecordingItem } from "@/lib/bindings";
import { formatDuration, formatDate } from "@/lib/format";
import { AiTaskBar } from "@/components/workspace/AiTaskBar";
import { AudioPlayer } from "@/components/workspace/AudioPlayer";
import { EditableAsset } from "@/components/workspace/EditableAsset";
import { Mic, Clock, Trash2 } from "lucide-react";

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

function DocumentPage() {
  const { documentId } = Route.useParams();
  const navigate = useNavigate();
  const [assets, setAssets] = useState<DocumentAsset[]>([]);
  const [recording, setRecording] = useState<RecordingItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [alsoDeleteDoc, setAlsoDeleteDoc] = useState(true);

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
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-2 min-w-0">
            <Mic className="w-4 h-4 shrink-0 text-accent-primary" />
            <h1 className="text-base font-semibold text-text-primary truncate">
              {recording?.title ?? "文档"}
            </h1>
          </div>

          {/* Delete button */}
          <button
            onClick={() => setShowDeleteConfirm(true)}
            className="shrink-0 p-1.5 rounded text-text-muted hover:text-status-error hover:bg-status-error/10 transition-colors"
            title="删除录音"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>

        {/* Metadata */}
        {recording && (
          <div className="flex items-center gap-3 mt-1 text-xs text-text-muted">
            <span>{formatDate(recording.created_at)}</span>
            <span className="flex items-center gap-1">
              <Clock className="w-3 h-3" />
              {formatDuration(recording.duration_ms)}
            </span>
          </div>
        )}

        {/* Audio player */}
        {recording && recording.file_path && (
          <div className="mt-3">
            <AudioPlayer
              key={recording.file_path}
              filePath={recording.file_path}
              durationMs={recording.duration_ms}
            />
          </div>
        )}

        {/* AI toolbar */}
        <div className="mt-3">
          <AiTaskBar documentId={documentId} />
        </div>
      </div>

      {/* Content sections */}
      <div className="flex-1 px-6 py-4 flex flex-col gap-5 overflow-y-auto">
        {assets.length === 0 ? (
          <p className="text-sm text-text-muted">
            暂无内容。录音结束后转写内容会自动显示，或点击上方 AI 工具生成摘要。
          </p>
        ) : (
          assets.map((asset) => {
            const meta = ROLE_META[asset.role] ?? {
              label: asset.role,
              order: 99,
            };
            return (
              <EditableAsset
                key={asset.id}
                documentId={documentId}
                role={asset.role}
                label={meta.label}
                initialContent={asset.content}
                onSaved={loadData}
              />
            );
          })
        )}
      </div>

      {/* Delete confirmation dialog */}
      {showDeleteConfirm && recording && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-bg-primary border border-border-default rounded-lg shadow-xl p-6 max-w-sm w-full mx-4">
            <h2 className="text-base font-semibold text-text-primary mb-2">
              删除录音
            </h2>
            <p className="text-sm text-text-secondary mb-4">
              「{recording.title}」将被永久删除，音频文件也会从磁盘移除。
            </p>

            <label className="flex items-center gap-2 mb-5 cursor-pointer">
              <input
                type="checkbox"
                checked={alsoDeleteDoc}
                onChange={(e) => setAlsoDeleteDoc(e.target.checked)}
                className="rounded"
              />
              <span className="text-sm text-text-primary">
                同时删除工作台文档（转写、摘要等内容）
              </span>
            </label>

            {!alsoDeleteDoc && (
              <p className="text-xs text-text-muted mb-4 -mt-3 ml-6">
                保留后仍可在工作台查看，但无法回放音频。
              </p>
            )}

            <div className="flex gap-3 justify-end">
              <button
                onClick={() => setShowDeleteConfirm(false)}
                className="px-4 py-2 text-sm rounded-md border border-border-default text-text-primary hover:bg-bg-secondary transition-colors"
              >
                取消
              </button>
              <button
                onClick={async () => {
                  const result = await commands.deleteRecording(
                    recording.id,
                    alsoDeleteDoc
                  );
                  if (result.status === "ok") {
                    navigate({ to: "/workspace" });
                  }
                  setShowDeleteConfirm(false);
                }}
                className="px-4 py-2 text-sm rounded-md bg-status-error text-white hover:opacity-90 transition-opacity"
              >
                删除
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
