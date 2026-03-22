// src/components/workspace/EditableAsset.tsx
// Editable section for one text asset: Preview ↔ Edit toggle + debounced autosave.
// Preview renders Markdown via react-markdown/remark-gfm.

import { useState, useEffect, useRef, useCallback } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { commands } from "@/lib/bindings";
import { Check, Loader2, Eye, Pencil } from "lucide-react";

interface EditableAssetProps {
  documentId: string;
  role: string;
  label: string;
  initialContent: string;
  /** Called after successful save so parent can refresh if needed */
  onSaved?: () => void;
}

type SaveState = "idle" | "saving" | "saved";

export function EditableAsset({
  documentId,
  role,
  label,
  initialContent,
  onSaved,
}: EditableAssetProps) {
  const [editing, setEditing] = useState(false);
  const [content, setContent] = useState(initialContent);
  const [saveState, setSaveState] = useState<SaveState>("idle");
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastSavedRef = useRef(initialContent);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Keep content in sync if parent reloads (e.g., AI task completes)
  useEffect(() => {
    if (content === lastSavedRef.current) {
      setContent(initialContent);
      lastSavedRef.current = initialContent;
    }
  }, [initialContent]);

  // Auto-focus textarea when entering edit mode
  useEffect(() => {
    if (editing) {
      textareaRef.current?.focus();
    }
  }, [editing]);

  const save = useCallback(
    async (text: string) => {
      if (text === lastSavedRef.current) return;
      setSaveState("saving");
      const result = await commands.updateDocumentAsset(documentId, role, text);
      if (result.status === "ok") {
        lastSavedRef.current = text;
        setSaveState("saved");
        onSaved?.();
        setTimeout(() => setSaveState("idle"), 2000);
      } else {
        setSaveState("idle");
        console.error("[EditableAsset] save failed:", result.error);
      }
    },
    [documentId, role, onSaved]
  );

  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const text = e.target.value;
    setContent(text);
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => save(text), 1500);
  };

  const handleBlur = () => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    save(content);
    setEditing(false);
  };

  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, []);

  return (
    <section className="flex flex-col gap-1.5">
      {/* Section header */}
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold text-text-secondary uppercase tracking-wide">
          {label}
        </span>

        <div className="flex items-center gap-2">
          {saveState === "saving" && (
            <span className="flex items-center gap-1 text-xs text-text-muted">
              <Loader2 className="w-3 h-3 animate-spin" />
              保存中…
            </span>
          )}
          {saveState === "saved" && (
            <span className="flex items-center gap-1 text-xs text-status-success">
              <Check className="w-3 h-3" />
              已保存
            </span>
          )}

          {/* Preview / Edit toggle */}
          <button
            onClick={() => setEditing((v) => !v)}
            className="flex items-center gap-1 px-1.5 py-0.5 rounded text-xs text-text-muted hover:text-text-primary hover:bg-bg-tertiary transition-colors"
            title={editing ? "预览" : "编辑"}
          >
            {editing ? <Eye className="w-3 h-3" /> : <Pencil className="w-3 h-3" />}
            {editing ? "预览" : "编辑"}
          </button>
        </div>
      </div>

      {/* Edit mode: textarea */}
      {editing ? (
        <textarea
          ref={textareaRef}
          value={content}
          onChange={handleChange}
          onBlur={handleBlur}
          className={[
            "w-full min-h-[160px] text-sm text-text-primary leading-relaxed",
            "rounded-md bg-bg-secondary border border-accent-primary p-3",
            "resize-y focus:outline-none",
            "placeholder:text-text-muted font-mono",
          ].join(" ")}
          placeholder={`在此输入${label}…`}
          spellCheck={false}
        />
      ) : (
        // Preview mode: Markdown rendered, click to edit
        <div
          onClick={() => setEditing(true)}
          className={[
            "w-full min-h-[80px] rounded-md border border-border-default p-3",
            "cursor-text hover:border-border-strong transition-colors",
            "prose prose-sm prose-invert max-w-none",
            "text-text-primary text-sm leading-relaxed",
          ].join(" ")}
        >
          {content.trim() ? (
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {content}
            </ReactMarkdown>
          ) : (
            <span className="text-text-muted">{`在此输入${label}…`}</span>
          )}
        </div>
      )}
    </section>
  );
}
