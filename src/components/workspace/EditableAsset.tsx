// src/components/workspace/EditableAsset.tsx
// Editable section for one text asset: Preview ↔ Edit toggle + debounced autosave.
// Preview renders Markdown via react-markdown/remark-gfm.

import { useState, useEffect, useRef, useCallback } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { commands } from "@/lib/bindings";
import { Check, Loader2, Pencil } from "lucide-react";

interface EditableAssetProps {
  documentId: string;
  role: string;
  label?: string;
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
    if (content === lastSavedRef.current && initialContent !== lastSavedRef.current) {
      setContent(initialContent);
      lastSavedRef.current = initialContent;
    }
  }, [initialContent, content]);

  // Auto-focus and resize textarea when entering edit mode
  useEffect(() => {
    if (editing && textareaRef.current) {
      textareaRef.current.focus();
      const len = textareaRef.current.value.length || 0;
      textareaRef.current.setSelectionRange(len, len);
      
      // Initial height adjustment
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = textareaRef.current.scrollHeight + "px";
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
    
    // Auto resize
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = textareaRef.current.scrollHeight + "px";
    }

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
    <section className="group relative flex flex-col pt-1 max-w-none">
      {/* Absolute Header (Only shows label and actions) */}
      <div className="absolute -top-7 right-0 flex items-center gap-3 opacity-0 group-hover:opacity-100 focus-within:opacity-100 transition-opacity z-10 bg-bg-primary/95 rounded-full px-3 py-1 border border-border-default/50 shadow-sm backdrop-blur-sm">
        {label && (
          <span className="text-[11px] font-semibold text-text-muted uppercase tracking-widest select-none pr-1 border-r border-border-default/50">
            {label}
          </span>
        )}

        {saveState === "saving" && (
          <span className="flex items-center gap-1.5 text-[11px] text-text-muted font-medium">
            <Loader2 className="w-3 h-3 animate-spin" />
            保存中…
          </span>
        )}
        {saveState === "saved" && (
          <span className="flex items-center gap-1.5 text-[11px] text-status-success font-medium">
            <Check className="w-3 h-3" />
            已保存
          </span>
        )}

        <button
          onClick={() => setEditing((v) => !v)}
          className="flex items-center gap-1 px-1.5 rounded text-[11px] text-text-muted hover:text-text-primary hover:bg-bg-tertiary transition-colors"
          title={editing ? "退出编辑" : "编辑"}
        >
          {editing ? <Check className="w-3 h-3" /> : <Pencil className="w-3 h-3" />}
          {editing ? "完成" : "编辑"}
        </button>
      </div>

      {/* Main Content Area */}
      <div className="relative w-full">
        {editing ? (
          <textarea
            ref={textareaRef}
            value={content}
            onChange={handleChange}
            onBlur={handleBlur}
            className={[
              "w-full min-h-[120px] resize-none overflow-hidden",
              "bg-transparent border-none outline-none ring-0",
              "text-text-primary text-base md:text-[17px] leading-relaxed font-sans",
              "placeholder:text-text-muted/40 p-0 m-0",
            ].join(" ")}
            placeholder={label ? `在此输入 ${label} 的内容...` : "开始编写..."}
            spellCheck={false}
          />
        ) : (
          <div
            onClick={(e) => {
              // Only trigger edit if clicking on the wrapper, not links
              if ((e.target as HTMLElement).tagName.toLowerCase() !== 'a') {
                setEditing(true);
              }
            }}
            className={[
              "w-full min-h-[80px]",
              "cursor-text transition-colors",
              "prose prose-base md:prose-lg dark:prose-invert max-w-none",
              "text-text-primary leading-relaxed font-sans",
              // Fine-tuning typography
              "prose-p:my-4 prose-p:leading-relaxed",
              "prose-headings:font-bold prose-headings:text-text-primary prose-headings:tracking-tight",
              "prose-a:text-accent-primary prose-a:no-underline hover:prose-a:underline",
              "prose-strong:text-text-primary prose-strong:font-semibold",
              "prose-ul:my-4 prose-li:my-1",
              "focus:outline-none"
            ].join(" ")}
          >
            {content.trim() ? (
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {content}
              </ReactMarkdown>
            ) : (
              <div className="text-text-muted/40 italic py-6 select-none border border-dashed border-border-default/40 rounded-xl flex items-center justify-center bg-bg-secondary/20 hover:bg-bg-secondary/40 transition-colors cursor-pointer">
                {label ? `暂无${label}` : "点击开始编写..."}
              </div>
            )}
          </div>
        )}
      </div>
    </section>
  );
}
