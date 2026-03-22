// src/routes/workspace.$documentId.tsx
// Document detail page.
// Layout:
//   Header:   icon + title + delete
//   Meta:     date · duration
//   Audio:    compact player
//   Toolbar:  AI task bar
//   ──────────────────────────────
//   Primary:  transcript / document_text — full Obsidian-style edit/preview
//   AI panel: 摘要 | 会议纪要 | 翻译  tabs  (only shown when AI content exists)

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

// ── Asset grouping ─────────────────────────────────────────────────────────

const PRIMARY_ROLES = new Set(["transcript", "document_text"]);

const AI_TABS = [
  { id: "summary",     label: "摘要",    roles: ["summary"] },
  { id: "meeting",     label: "会议纪要", roles: ["meeting_brief", "decisions", "action_items", "next_steps"] },
  { id: "translation", label: "翻译",    roles: ["translation"] },
] as const;

type AiTabId = (typeof AI_TABS)[number]["id"];

// ── Role display metadata ──────────────────────────────────────────────────

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

// ── DocumentPage ──────────────────────────────────────────────────────────

function DocumentPage() {
  const { documentId } = Route.useParams();
  const navigate = useNavigate();
  const [assets, setAssets] = useState<DocumentAsset[]>([]);
  const [recording, setRecording] = useState<RecordingItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [alsoDeleteDoc, setAlsoDeleteDoc] = useState(true);
  const [activeAiTab, setActiveAiTab] = useState<AiTabId | null>(null);

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
    if (assetsResult.status === "ok") setAssets(sortAssets(assetsResult.data));
    if (recordingsResult.status === "ok") {
      const rec = recordingsResult.data.find((r) => r.document_id === documentId);
      setRecording(rec ?? null);
    }
    setLoading(false);
  }, [documentId, sortAssets]);

  useEffect(() => { loadData(); }, [loadData]);

  // Poll for new assets after AI tasks complete
  useEffect(() => {
    const timer = setInterval(async () => {
      const result = await commands.getDocumentAssets(documentId);
      if (result.status === "ok") setAssets(sortAssets(result.data));
    }, 3000);
    return () => clearInterval(timer);
  }, [documentId, sortAssets]);

  // ── Derived groupings ────────────────────────────────────────────────────

  const primaryAssets = assets.filter((a) => PRIMARY_ROLES.has(a.role));
  const aiAssets = assets.filter((a) => !PRIMARY_ROLES.has(a.role));

  const visibleTabs = AI_TABS.filter((tab) =>
    tab.roles.some((role) => aiAssets.some((a) => a.role === role))
  );

  // Auto-select first available tab when AI content arrives
  useEffect(() => {
    if (visibleTabs.length > 0 && !activeAiTab) {
      setActiveAiTab(visibleTabs[0].id);
    }
    if (activeAiTab && !visibleTabs.some((t) => t.id === activeAiTab) && visibleTabs.length > 0) {
      setActiveAiTab(visibleTabs[0].id);
    }
  }, [visibleTabs.length, activeAiTab]);

  const activeTabDef = AI_TABS.find((t) => t.id === activeAiTab);
  const activeTabAssets = activeTabDef
    ? activeTabDef.roles.flatMap((role) => aiAssets.filter((a) => a.role === role))
    : [];

  // ── Render ────────────────────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center text-text-muted text-sm">
        加载中…
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* ── Header ─────────────────────────────────────────────────── */}
      <div className="shrink-0 px-6 py-4 border-b border-border-default space-y-2">
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-2 min-w-0">
            <Mic className="w-4 h-4 shrink-0 text-accent-primary" />
            <h1 className="text-base font-semibold text-text-primary truncate">
              {recording?.title ?? "文档"}
            </h1>
          </div>
          <button
            onClick={() => setShowDeleteConfirm(true)}
            className="shrink-0 p-1.5 rounded text-text-muted hover:text-status-error hover:bg-status-error/10 transition-colors"
            title="删除录音"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>

        {recording && (
          <div className="flex items-center gap-3 text-xs text-text-muted">
            <span>{formatDate(recording.created_at)}</span>
            <span className="flex items-center gap-1">
              <Clock className="w-3 h-3" />
              {formatDuration(recording.duration_ms)}
            </span>
          </div>
        )}

        {recording?.file_path && (
          <AudioPlayer key={recording.file_path} filePath={recording.file_path} durationMs={recording.duration_ms} />
        )}

        <AiTaskBar documentId={documentId} />
      </div>

      {/* ── Body ───────────────────────────────────────────────────── */}
      <div className="flex-1 flex flex-col overflow-hidden min-h-0">

        {/* Primary: transcript / document_text */}
        <div className="flex-1 overflow-y-auto min-h-0 px-6 py-4 space-y-4">
          {primaryAssets.length === 0 ? (
            <p className="text-sm text-text-muted">
              暂无内容。录音结束后转写内容会自动显示，或点击上方 AI 工具生成摘要。
            </p>
          ) : (
            primaryAssets.map((asset) => {
              const meta = ROLE_META[asset.role] ?? { label: asset.role, order: 99 };
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

        {/* AI tabs panel — only shown when AI content exists */}
        {visibleTabs.length > 0 && (
          <div className="shrink-0 flex flex-col border-t border-border-default" style={{ maxHeight: "45%" }}>

            {/* Tab bar */}
            <div className="shrink-0 flex items-center border-b border-border-default bg-bg-secondary px-2">
              {visibleTabs.map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveAiTab(tab.id)}
                  className={[
                    "px-3 py-2 text-xs font-medium transition-colors border-b-2 -mb-px",
                    activeAiTab === tab.id
                      ? "border-accent-primary text-accent-primary"
                      : "border-transparent text-text-muted hover:text-text-primary",
                  ].join(" ")}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            {/* Tab content */}
            <div className="flex-1 overflow-y-auto min-h-0 px-6 py-3 space-y-4">
              {activeTabAssets.map((asset) => {
                const meta = ROLE_META[asset.role] ?? { label: asset.role, order: 99 };
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
              })}
            </div>
          </div>
        )}
      </div>

      {/* ── Delete confirmation ─────────────────────────────────────── */}
      {showDeleteConfirm && recording && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-bg-primary border border-border-default rounded-lg shadow-xl p-6 max-w-sm w-full mx-4">
            <h2 className="text-base font-semibold text-text-primary mb-2">删除录音</h2>
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
              <span className="text-sm text-text-primary">同时删除工作台文档（转写、摘要等内容）</span>
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
                  const result = await commands.deleteRecording(recording.id, alsoDeleteDoc);
                  if (result.status === "ok") navigate({ to: "/workspace" });
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
