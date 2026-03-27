import { useEffect, useRef, useState } from "react";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Check, Loader2, Pencil } from "lucide-react";

import { commands } from "@/lib/bindings";

interface EditableAssetProps {
  documentId: string;
  role: string;
  label?: string;
  actionLabel?: string;
  initialContent: string;
  onSaved?: () => void;
}

type SaveState = "idle" | "saving" | "saved";

export function EditableAsset({
  documentId,
  role,
  label,
  actionLabel = "编辑",
  initialContent,
  onSaved,
}: EditableAssetProps) {
  const [editing, setEditing] = useState(false);
  const [content, setContent] = useState(initialContent);
  const [saveState, setSaveState] = useState<SaveState>("idle");
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const savedResetRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastSavedRef = useRef(initialContent);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (content === lastSavedRef.current && initialContent !== lastSavedRef.current) {
      setContent(initialContent);
      lastSavedRef.current = initialContent;
    }
  }, [initialContent, content]);

  useEffect(() => {
    if (editing && textareaRef.current) {
      textareaRef.current.focus();
      const len = textareaRef.current.value.length || 0;
      textareaRef.current.setSelectionRange(len, len);
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
    }
  }, [editing]);

  useEffect(() => {
    return () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current);
      }
      if (savedResetRef.current) {
        clearTimeout(savedResetRef.current);
      }
    };
  }, []);

  const save = async (text: string) => {
    if (text === lastSavedRef.current) {
      return;
    }

    setSaveState("saving");
    const result = await commands.updateDocumentAsset(documentId, role, text);
    if (result.status === "ok") {
      lastSavedRef.current = text;
      setSaveState("saved");
      onSaved?.();
      if (savedResetRef.current) {
        clearTimeout(savedResetRef.current);
      }
      savedResetRef.current = setTimeout(() => {
        setSaveState("idle");
      }, 2000);
      return;
    }

    setSaveState("idle");
    console.error("[EditableAsset] save failed:", result.error);
  };

  const handleChange = (event: React.ChangeEvent<HTMLTextAreaElement>) => {
    const text = event.target.value;
    setContent(text);

    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
    }

    if (timerRef.current) {
      clearTimeout(timerRef.current);
    }
    timerRef.current = setTimeout(() => void save(text), 1500);
  };

  const handleBlur = () => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }

    void save(content);
    setEditing(false);
  };

  return (
    <section className="flex flex-col gap-3 rounded-xl border border-border/70 bg-bg-secondary/20 p-4">
      <div className="flex items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2">
          <span className="truncate text-xs font-semibold uppercase tracking-[0.24em] text-text-muted">
            {label ?? "内容"}
          </span>
          {saveState === "saving" && (
            <span className="flex items-center gap-1 text-[11px] text-text-muted">
              <Loader2 className="h-3 w-3 animate-spin" />
              保存中…
            </span>
          )}
          {saveState === "saved" && (
            <span className="flex items-center gap-1 text-[11px] text-status-success">
              <Check className="h-3 w-3" />
              已保存
            </span>
          )}
        </div>

        <button
          type="button"
          onClick={() => setEditing((value) => !value)}
          className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium text-text-muted transition-colors hover:bg-bg-tertiary hover:text-text-primary"
          title={editing ? "退出编辑" : actionLabel}
        >
          {editing ? <Check className="h-3 w-3" /> : <Pencil className="h-3 w-3" />}
          {editing ? "完成" : actionLabel}
        </button>
      </div>

      {editing ? (
        <textarea
          ref={textareaRef}
          value={content}
          onChange={handleChange}
          onBlur={handleBlur}
          className={[
            "min-h-[120px] w-full resize-none overflow-hidden rounded-xl border border-border/60",
            "bg-bg-primary/80 px-3 py-3 text-base leading-relaxed text-text-primary outline-none",
            "placeholder:text-text-muted/40 focus:border-accent/60",
          ].join(" ")}
          placeholder={label ? `在此输入${label}` : "开始编写..."}
          spellCheck={false}
        />
      ) : (
        <div
          onClick={(event) => {
            if ((event.target as HTMLElement).tagName.toLowerCase() !== "a") {
              setEditing(true);
            }
          }}
          className={[
            "min-h-[80px] cursor-text rounded-xl border border-transparent px-1 py-1 transition-colors",
            "text-text-primary",
            "hover:border-border/60 hover:bg-bg-primary/40",
          ].join(" ")}
        >
          {content.trim() ? (
            <div className="prose prose-base dark:prose-invert max-w-none text-text-primary">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
            </div>
          ) : (
            <div className="flex min-h-[80px] items-center justify-center rounded-lg border border-dashed border-border/40 bg-bg-secondary/20 px-4 py-6 text-sm italic text-text-muted/50">
              {label ? `暂无${label}` : "点击开始编写..."}
            </div>
          )}
        </div>
      )}
    </section>
  );
}
