// src/routes/workspace.$documentId.tsx
// Obsidian-style document page:
//   Header: source icon + inline-editable title + AI panel + delete
//   Meta:   date · duration · folder breadcrumb
//   Audio:  compact player (recording only)
//   Body:   Primary = transcript/document_text (full Obsidian edit/preview)
//           AI tabs = 摘要 | 会议纪要 | 翻译  (only rendered when content exists)

import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState, useCallback, useRef } from "react";
import { useNavigate } from "@tanstack/react-router";
import { commands } from "@/lib/bindings";
import type { DocumentAsset, RecordingItem } from "@/lib/bindings";
import { formatDuration, formatDate } from "@/lib/format";
import { AiPanel } from "@/components/workspace/AiPanel";
import { AudioPlayer } from "@/components/workspace/AudioPlayer";
import { EditableAsset } from "@/components/workspace/EditableAsset";
import type { EditableAssetHandle } from "@/components/workspace/EditableAsset";
import { SubtitleEditor } from "@/components/workspace/SubtitleEditor";
import { useWorkspaceStore } from "@/store/workspace";
import { Mic, Clock, FileText, Trash2, FileType2, Captions } from "lucide-react";

type DocMode = "document" | "subtitle";

export const Route = createFileRoute("/workspace/$documentId")({
  component: DocumentPage,
});

// ── Asset grouping ─────────────────────────────────────────────────────────

/** Roles shown in the primary Obsidian-style editable area */
const PRIMARY_ROLES = new Set(["transcript", "document_text"]);

/** AI tab definitions — order matters for display */
const AI_TABS = [
  {
    id: "summary",
    label: "摘要",
    roles: ["summary"],
  },
  {
    id: "meeting",
    label: "会议纪要",
    roles: ["meeting_brief", "decisions", "action_items", "next_steps"],
  },
  {
    id: "translation",
    label: "翻译",
    roles: ["translation"],
  },
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

// ── Helpers ────────────────────────────────────────────────────────────────

function findFolderName(
  tree: ReturnType<typeof useWorkspaceStore.getState>["folderTree"],
  documentId: string
): string | null {
  for (const node of tree) {
    if (node.documents.some((d) => d.id === documentId)) return node.name;
    const found = findFolderName(node.children, documentId);
    if (found) return found;
  }
  return null;
}

// ── DocumentPage ──────────────────────────────────────────────────────────

function DocumentPage() {
  const { documentId } = Route.useParams();
  const navigate = useNavigate();
  const { folderTree, renameDocument: storeRename } = useWorkspaceStore();

  const [mode, setMode] = useState<DocMode>("document");
  const [assets, setAssets] = useState<DocumentAsset[]>([]);
  const [recording, setRecording] = useState<RecordingItem | null>(null);
  const [loading, setLoading] = useState(true);

  // Inline title editing
  const [titleValue, setTitleValue] = useState("");
  const [titleEditing, setTitleEditing] = useState(false);
  const titleInputRef = useRef<HTMLInputElement>(null);

  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [alsoDeleteDoc, setAlsoDeleteDoc] = useState(true);

  // EditableAsset refs (keyed by role) for insert-at-cursor
  const assetRefs = useRef<Map<string, EditableAssetHandle>>(new Map());
  const lastFocusedRoleRef = useRef<string | null>(null);

  // Active AI tab
  const [activeAiTab, setActiveAiTab] = useState<AiTabId | null>(null);

  const folderName = findFolderName(folderTree, documentId);

  const sortAssets = useCallback(
    (raw: DocumentAsset[]) =>
      [...raw].sort((a, b) => {
        const ao = ROLE_META[a.role]?.order ?? 99;
        const bo = ROLE_META[b.role]?.order ?? 99;
        return ao - bo;
      }),
    []
  );

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
      if (rec && !titleValue) setTitleValue(rec.title);
    }

    setLoading(false);
  }, [documentId, sortAssets]);

  // Seed title from folderTree (fast, no extra fetch needed)
  useEffect(() => {
    for (const node of folderTree) {
      const doc = node.documents.find((d) => d.id === documentId);
      if (doc) { setTitleValue(doc.title); return; }
    }
  }, [folderTree, documentId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

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

  // Only show tabs that have at least one matching asset
  const visibleTabs = AI_TABS.filter((tab) =>
    tab.roles.some((role) => aiAssets.some((a) => a.role === role))
  );

  // Auto-select first available tab when AI content arrives
  useEffect(() => {
    if (visibleTabs.length > 0 && !activeAiTab) {
      setActiveAiTab(visibleTabs[0].id);
    }
    // If active tab's content was removed, reset to first
    if (
      activeAiTab &&
      !visibleTabs.some((t) => t.id === activeAiTab) &&
      visibleTabs.length > 0
    ) {
      setActiveAiTab(visibleTabs[0].id);
    }
  }, [visibleTabs.length, activeAiTab]);

  const activeTabDef = AI_TABS.find((t) => t.id === activeAiTab);
  const activeTabAssets = activeTabDef
    ? activeTabDef.roles.flatMap((role) => aiAssets.filter((a) => a.role === role))
    : [];

  // ── Title handlers ────────────────────────────────────────────────────────

  const handleTitleBlur = useCallback(async () => {
    setTitleEditing(false);
    const trimmed = titleValue.trim();
    if (!trimmed) return;
    const current =
      folderTree
        .flatMap((n) => [...n.documents, ...n.children.flatMap((c) => c.documents)])
        .find((d) => d.id === documentId)?.title ?? recording?.title;
    if (trimmed !== current) {
      await storeRename(documentId, trimmed);
    }
  }, [titleValue, documentId, folderTree, recording, storeRename]);

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center text-text-muted text-sm">
        加载中…
      </div>
    );
  }

  const isRecording = !!recording;

  return (
    <div className="flex flex-col h-full">
      {/* ── Document header ─────────────────────────────────────────── */}
      <div className="shrink-0 px-6 py-3 border-b border-border-default space-y-1.5">

        {/* Title row */}
        <div className="flex items-center gap-2 min-w-0">
          {isRecording ? (
            <Mic className="w-4 h-4 shrink-0 text-accent-primary" />
          ) : (
            <FileText className="w-4 h-4 shrink-0 text-text-secondary" />
          )}

          <input
            ref={titleInputRef}
            value={titleValue}
            readOnly={!titleEditing}
            onChange={(e) => setTitleValue(e.target.value)}
            onClick={() => setTitleEditing(true)}
            onBlur={handleTitleBlur}
            onKeyDown={(e) => {
              if (e.key === "Enter") titleInputRef.current?.blur();
              if (e.key === "Escape") {
                setTitleEditing(false);
                const orig =
                  folderTree
                    .flatMap((n) => [...n.documents, ...n.children.flatMap((c) => c.documents)])
                    .find((d) => d.id === documentId)?.title ?? recording?.title ?? "";
                setTitleValue(orig);
              }
            }}
            className={[
              "flex-1 min-w-0 bg-transparent text-base font-semibold text-text-primary",
              "focus:outline-none truncate cursor-default",
              titleEditing
                ? "border-b border-accent-primary cursor-text"
                : "hover:border-b hover:border-border-strong",
            ].join(" ")}
          />

          {/* Mode switcher (only when recording has a file) */}
          {recording?.file_path && (
            <div className="flex items-center rounded border border-border-default overflow-hidden">
              <button
                onClick={() => setMode("document")}
                className={[
                  "flex items-center gap-1 px-2 py-1 text-xs transition-colors",
                  mode === "document"
                    ? "bg-accent-primary/15 text-accent-primary"
                    : "text-text-muted hover:bg-bg-tertiary",
                ].join(" ")}
                title="文档模式"
              >
                <FileType2 className="w-3 h-3" />
                文档
              </button>
              <button
                onClick={() => setMode("subtitle")}
                className={[
                  "flex items-center gap-1 px-2 py-1 text-xs transition-colors border-l border-border-default",
                  mode === "subtitle"
                    ? "bg-accent-primary/15 text-accent-primary"
                    : "text-text-muted hover:bg-bg-tertiary",
                ].join(" ")}
                title="字幕模式"
              >
                <Captions className="w-3 h-3" />
                字幕
              </button>
            </div>
          )}

          {/* AI panel trigger */}
          <AiPanel
            documentId={documentId}
            onInsertAtCursor={(text) => {
              const role = lastFocusedRoleRef.current ?? primaryAssets[0]?.role;
              if (role) assetRefs.current.get(role)?.insertAtCursor(text);
            }}
          />

          {/* Delete */}
          <button
            onClick={() => setShowDeleteConfirm(true)}
            className="shrink-0 p-1 rounded text-text-muted hover:text-status-error hover:bg-status-error/10 transition-colors"
            title="删除"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>

        {/* Meta row */}
        <div className="flex items-center gap-1.5 text-xs text-text-muted">
          <span>{formatDate(recording?.created_at ?? 0)}</span>
          {recording && (
            <>
              <span>·</span>
              <span className="flex items-center gap-0.5">
                <Clock className="w-3 h-3" />
                {formatDuration(recording.duration_ms)}
              </span>
            </>
          )}
          {folderName && (
            <>
              <span>·</span>
              <span>{folderName}</span>
            </>
          )}
        </div>

        {/* Compact audio player — hidden in subtitle mode */}
        {recording?.file_path && mode === "document" && (
          <AudioPlayer
            key={recording.file_path}
            filePath={recording.file_path}
            durationMs={recording.duration_ms}
          />
        )}
      </div>

      {/* ── Subtitle mode ────────────────────────────────────────── */}
      {mode === "subtitle" && recording?.file_path && (
        <SubtitleEditor
          recordingId={recording.id}
          filePath={recording.file_path}
          durationMs={recording.duration_ms}
        />
      )}

      {/* ── Document mode ─────────────────────────────────────────── */}
      {mode === "document" && (
        <div className="flex-1 flex flex-col overflow-hidden min-h-0">

          {/* Primary content: transcript / document_text (Obsidian-style main area) */}
          <div className="flex-1 overflow-y-auto min-h-0 px-6 py-4">
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
                    ref={(h) => {
                      if (h) assetRefs.current.set(asset.role, h);
                      else assetRefs.current.delete(asset.role);
                    }}
                    documentId={documentId}
                    role={asset.role}
                    label={meta.label}
                    initialContent={asset.content}
                    onSaved={loadData}
                    onFocusChange={(focused) => {
                      if (focused) lastFocusedRoleRef.current = asset.role;
                    }}
                  />
                );
              })
            )}
          </div>

          {/* AI tabs panel — only shown when AI-generated content exists */}
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
              <div className="flex-1 overflow-y-auto min-h-0 px-6 py-3">
                {activeTabAssets.length === 0 ? (
                  <p className="text-sm text-text-muted py-4 text-center">暂无内容</p>
                ) : (
                  activeTabAssets.map((asset, idx) => {
                    const meta = ROLE_META[asset.role] ?? { label: asset.role, order: 99 };
                    return (
                      <div key={asset.id}>
                        {idx > 0 && <hr className="border-border-default my-3" />}
                        <EditableAsset
                          ref={(h) => {
                            if (h) assetRefs.current.set(asset.role, h);
                            else assetRefs.current.delete(asset.role);
                          }}
                          documentId={documentId}
                          role={asset.role}
                          label={meta.label}
                          initialContent={asset.content}
                          onSaved={loadData}
                          onFocusChange={(focused) => {
                            if (focused) lastFocusedRoleRef.current = asset.role;
                          }}
                        />
                      </div>
                    );
                  })
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── Delete confirmation ──────────────────────────────────── */}
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
