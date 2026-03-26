// src/routes/workspace.$documentId.tsx
// Document detail page.
// Layout:
//   Unified scrolling Notion-like page.
//   Top: Huge Title, Meta, Audio Player, AI Actions
//   Tabs (optional, only if AI contents exist)
//   Content: max-w-3xl centered

import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState, useCallback, useRef } from "react";
import { useNavigate } from "@tanstack/react-router";
import { commands } from "@/lib/bindings";
import type { DocumentAsset, RecordingItem } from "@/lib/bindings";
import { formatDuration, formatDate } from "@/lib/format";
import { AiTaskBar } from "@/components/workspace/AiTaskBar";
import { AudioPlayer } from "@/components/workspace/AudioPlayer";
import { EditableAsset } from "@/components/workspace/EditableAsset";
import { Clock, Trash2, CalendarDays } from "lucide-react";

export const Route = createFileRoute("/workspace/$documentId")({
  component: DocumentPage,
});

// ── Asset grouping ─────────────────────────────────────────────────────────

const VIEW_TABS = [
  { id: "primary",     label: "文档",    roles: ["document_text", "transcript"] },
  { id: "summary",     label: "摘要",    roles: ["summary"] },
  { id: "meeting",     label: "会议纪要", roles: ["meeting_brief", "decisions", "action_items", "next_steps"] },
  { id: "translation", label: "翻译",    roles: ["translation"] },
] as const;

type TabId = (typeof VIEW_TABS)[number]["id"];

// ── Role display metadata ──────────────────────────────────────────────────

const ROLE_META: Record<string, { label: string; order: number }> = {
  document_text: { label: "文档正文",  order: 0 },
  transcript:    { label: "转写原文",  order: 1 },
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
  const [activeTab, setActiveTab] = useState<TabId>("primary");
  const scrollRef = useRef<HTMLDivElement>(null);

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

  // Reset scroll on document change
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = 0;
    }
  }, [documentId]);

  // ── Derived groupings ────────────────────────────────────────────────────

  const visibleTabs = VIEW_TABS.filter((tab) =>
    tab.roles.some((role) => assets.some((a) => a.role === role))
  );

  // Auto-fallback for tabs
  useEffect(() => {
    if (visibleTabs.length > 0 && !visibleTabs.some((t) => t.id === activeTab)) {
      setActiveTab(visibleTabs[0].id);
    } else if (visibleTabs.length === 0 && activeTab !== "primary") {
      setActiveTab("primary");
    }
  }, [visibleTabs, activeTab]);

  const activeTabDef = VIEW_TABS.find((t) => t.id === activeTab) || VIEW_TABS[0];
  const activeAssets = activeTabDef.roles.flatMap((role) => assets.filter((a) => a.role === role));

  // ── Render ────────────────────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center text-text-muted text-sm border-none bg-bg-primary">
        加载中…
      </div>
    );
  }

  return (
    <div ref={scrollRef} className="flex flex-col h-full overflow-y-auto bg-bg-primary scroll-smooth">
      <div className="mx-auto w-full max-w-4xl px-8 py-12 md:py-16 flex flex-col gap-6 font-sans">
        
        {/* ── Header ─────────────────────────────────────────────────── */}
        <div className="group relative flex flex-col gap-4">
          <div className="flex items-start justify-between">
            <h1 className="text-3xl md:text-4xl font-extrabold text-text-primary leading-tight tracking-tight break-words pr-8">
              {recording?.title ?? "无标题文档"}
            </h1>
            <button
              onClick={() => setShowDeleteConfirm(true)}
              className="shrink-0 p-2 rounded-md text-text-muted opacity-0 group-hover:opacity-100 focus:opacity-100 hover:text-status-error hover:bg-status-error/10 transition-all absolute top-1 right-0"
              title="删除录音"
            >
              <Trash2 className="w-5 h-5" />
            </button>
          </div>

          {recording && (
            <div className="flex items-center gap-4 text-sm font-medium text-text-muted/70">
              <span className="flex items-center gap-1.5 focus:outline-none select-none">
                <CalendarDays className="w-4 h-4 opacity-60" />
                {formatDate(recording.created_at)}
              </span>
              <span className="flex items-center gap-1.5 select-none">
                <Clock className="w-4 h-4 opacity-60" />
                {formatDuration(recording.duration_ms)}
              </span>
            </div>
          )}
        </div>

        {recording?.file_path && (
          <div className="bg-bg-secondary/30 rounded-lg p-2 self-start w-full transition-colors hover:bg-bg-secondary/60">
            <AudioPlayer key={recording.file_path} filePath={recording.file_path} durationMs={recording.duration_ms} />
          </div>
        )}

        <div className="mt-4 pb-2 border-b border-border-default/50">
          <AiTaskBar documentId={documentId} />
        </div>

        {/* ── Body ───────────────────────────────────────────────────── */}
        <div className="mt-2 text-base md:text-lg leading-relaxed text-text-primary">
          {/* Tabs */}
          {visibleTabs.length > 1 && (
            <div className="flex items-center gap-6 border-b border-border-default mb-8 select-none">
              {visibleTabs.map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={[
                    "py-2 font-medium transition-all text-sm tracking-wide -mb-px",
                    activeTab === tab.id
                      ? "border-b-2 border-text-primary text-text-primary"
                      : "border-b-2 border-transparent text-text-muted hover:text-text-primary",
                  ].join(" ")}
                >
                  {tab.label}
                </button>
              ))}
            </div>
          )}

          {/* Asset List */}
          <div className="flex flex-col gap-10 min-h-[300px]">
            {activeAssets.length === 0 ? (
              activeTab === "primary" ? (
                <p className="text-sm text-text-muted/60 italic py-4 select-none">
                  录音结束或转写完成后，该区域将显示文本。点击上方按钮生成摘要。
                </p>
              ) : null
            ) : (
              activeAssets.map((asset) => {
                const meta = ROLE_META[asset.role] ?? { label: asset.role, order: 99 };
                // If it's the primary tab, we might show the label only if both text and transcript exist
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
        </div>

      </div>

      {/* ── Delete confirmation ─────────────────────────────────────── */}
      {showDeleteConfirm && recording && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="bg-bg-primary border border-border-default rounded-xl shadow-2xl p-6 max-w-sm w-full mx-4 shadow-black/20">
            <h2 className="text-lg font-semibold text-text-primary mb-3">删除录音</h2>
            <p className="text-sm text-text-secondary mb-5 leading-relaxed">
              「{recording.title}」将被永久删除，音频文件也会从磁盘移除。
            </p>
            <label className="flex items-center gap-2 mb-6 cursor-pointer group select-none">
              <input
                type="checkbox"
                checked={alsoDeleteDoc}
                onChange={(e) => setAlsoDeleteDoc(e.target.checked)}
                className="rounded border-border focus:ring-accent-primary"
              />
              <span className="text-sm text-text-primary group-hover:text-accent-primary transition-colors">同时删除文档资料（原文、摘要等）</span>
            </label>
            {!alsoDeleteDoc && (
              <p className="text-xs text-text-muted/70 mb-5 -mt-3 ml-6 select-none">
                保留后仍可在工作台查看文本记录，但无法回放音频。
              </p>
            )}
            <div className="flex gap-3 justify-end">
              <button
                onClick={() => setShowDeleteConfirm(false)}
                className="px-4 py-2 text-sm font-medium rounded-lg border border-border-default text-text-primary hover:bg-bg-secondary transition-colors"
              >
                取消
              </button>
              <button
                onClick={async () => {
                  const result = await commands.deleteRecording(recording.id, alsoDeleteDoc);
                  if (result.status === "ok") navigate({ to: "/workspace" });
                  setShowDeleteConfirm(false);
                }}
                className="px-4 py-2 text-sm font-medium rounded-lg bg-status-error text-white hover:bg-red-600 transition-colors shadow-sm"
              >
                永久删除
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
