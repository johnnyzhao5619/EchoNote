// src/components/workspace/EditableAsset.tsx
// Dual-mode editable section: click to edit Markdown, blur/Escape to preview.
// Exposes a `focus()` handle via forwardRef so parent can enter edit mode programmatically.

import {
  useState,
  useEffect,
  useRef,
  useCallback,
  forwardRef,
  useImperativeHandle,
} from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { commands } from "@/lib/bindings";
import { ChevronDown, ChevronRight, Check, Loader2, Pencil } from "lucide-react";
import { AiInlineToolbar } from "./AiInlineToolbar";

// ── Public handle ─────────────────────────────────────────────────────────────

export interface EditableAssetHandle {
  /** Programmatically enter edit mode and focus the textarea. */
  focus: () => void;
  /** Insert text at the current cursor/selection position in the textarea. */
  insertAtCursor: (text: string) => void;
}

// ── Props ─────────────────────────────────────────────────────────────────────

interface EditableAssetProps {
  documentId: string;
  role: string;
  label: string;
  initialContent: string;
  /** Called after successful save so parent can refresh if needed */
  onSaved?: () => void;
  /** Called when the component enters or leaves edit mode */
  onFocusChange?: (editing: boolean) => void;
}

type SaveState = "idle" | "saving" | "saved";

// ── Component ─────────────────────────────────────────────────────────────────

export const EditableAsset = forwardRef<EditableAssetHandle, EditableAssetProps>(
  function EditableAsset({ documentId, role, label, initialContent, onSaved, onFocusChange }, ref) {
    const [open, setOpen] = useState(true);
    const [editing, setEditing] = useState(false);
    const [content, setContent] = useState(initialContent);
    const [saveState, setSaveState] = useState<SaveState>("idle");

    const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const lastSavedRef = useRef(initialContent);
    const textareaRef = useRef<HTMLTextAreaElement>(null);

    // Expose focus() and insertAtCursor() to parent
    useImperativeHandle(ref, () => ({
      focus: () => {
        setOpen(true);
        setEditing(true);
        onFocusChange?.(true);
      },
      insertAtCursor: (text: string) => {
        const el = textareaRef.current;
        if (!el) return;
        setOpen(true);
        setEditing(true);
        onFocusChange?.(true);
        // Use rAF to ensure textarea is mounted before inserting
        requestAnimationFrame(() => {
          const ta = textareaRef.current;
          if (!ta) return;
          const start = ta.selectionStart;
          const end = ta.selectionEnd;
          ta.setRangeText(text, start, end, "end");
          // Trigger React onChange path
          const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
            window.HTMLTextAreaElement.prototype,
            "value"
          )?.set;
          nativeInputValueSetter?.call(ta, ta.value);
          ta.dispatchEvent(new Event("input", { bubbles: true }));
          setContent(ta.value);
          if (timerRef.current) clearTimeout(timerRef.current);
          timerRef.current = setTimeout(() => save(ta.value), 1500);
        });
      },
    }));

    // Focus textarea when entering edit mode
    useEffect(() => {
      if (editing && textareaRef.current) {
        textareaRef.current.focus();
        // Place cursor at end
        const len = textareaRef.current.value.length;
        textareaRef.current.setSelectionRange(len, len);
      }
    }, [editing]);

    // Sync external initialContent updates (e.g., AI task completed)
    useEffect(() => {
      if (content === lastSavedRef.current) {
        setContent(initialContent);
        lastSavedRef.current = initialContent;
      }
    }, [initialContent]);

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

    const exitEdit = () => {
      setEditing(false);
      onFocusChange?.(false);
      // Flush pending debounce immediately on blur
      if (timerRef.current) {
        clearTimeout(timerRef.current);
        timerRef.current = null;
        save(content);
      }
    };

    const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Escape") {
        e.preventDefault();
        exitEdit();
      }
    };

    // Clear timer on unmount
    useEffect(() => {
      return () => {
        if (timerRef.current) clearTimeout(timerRef.current);
      };
    }, []);

    return (
      <section className="flex flex-col gap-2">
        {/* Section header */}
        <div className="flex items-center justify-between">
          <button
            className="flex items-center gap-1.5 text-xs font-semibold text-text-secondary uppercase tracking-wide hover:text-text-primary transition-colors"
            onClick={() => setOpen((v) => !v)}
          >
            {open ? (
              <ChevronDown className="w-3.5 h-3.5" />
            ) : (
              <ChevronRight className="w-3.5 h-3.5" />
            )}
            {label}
          </button>

          <div className="flex items-center gap-2">
            {/* Save indicator */}
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

            {/* Edit toggle (only when open) */}
            {open && !editing && (
              <button
                onClick={() => { setEditing(true); onFocusChange?.(true); }}
                className="flex items-center justify-center w-5 h-5 rounded hover:bg-bg-tertiary text-text-muted"
                title="编辑"
              >
                <Pencil className="w-3 h-3" />
              </button>
            )}
          </div>
        </div>

        {/* Body */}
        {open && (
          <>
            {editing ? (
              /* Edit mode — raw textarea + inline toolbar */
              <>
                <AiInlineToolbar textareaRef={textareaRef} />
                <textarea
                  ref={textareaRef}
                  value={content}
                  onChange={handleChange}
                  onBlur={exitEdit}
                  onKeyDown={handleKeyDown}
                  className={[
                    "w-full min-h-[160px] text-sm text-text-primary leading-relaxed",
                    "rounded-md bg-bg-secondary border border-accent-primary p-3",
                    "resize-y focus:outline-none font-mono",
                  ].join(" ")}
                  placeholder={`在此输入${label}…`}
                  spellCheck={false}
                />
              </>
            ) : (
              /* Preview mode — rendered Markdown */
              <div
                role="button"
                tabIndex={0}
                onClick={() => { setEditing(true); onFocusChange?.(true); }}
                onKeyDown={(e) => e.key === "Enter" && (setEditing(true), onFocusChange?.(true))}
                className={[
                  "w-full min-h-[80px] text-sm text-text-primary leading-relaxed",
                  "rounded-md bg-bg-secondary border border-border-default p-3 cursor-text",
                  "hover:border-border-strong transition-colors",
                  "prose prose-sm prose-invert max-w-none",
                  // custom overrides to match app theme
                  "[&_p]:text-text-primary [&_p]:my-1",
                  "[&_h1]:text-text-primary [&_h2]:text-text-primary [&_h3]:text-text-primary",
                  "[&_ul]:text-text-primary [&_ol]:text-text-primary",
                  "[&_code]:bg-bg-tertiary [&_code]:px-1 [&_code]:rounded [&_code]:text-accent-primary",
                  "[&_pre]:bg-bg-tertiary [&_pre]:rounded [&_pre]:p-3",
                  "[&_blockquote]:border-l-2 [&_blockquote]:border-accent-primary [&_blockquote]:pl-3 [&_blockquote]:text-text-secondary",
                  "[&_a]:text-accent-primary [&_a]:underline",
                  "[&_hr]:border-border-default",
                  "[&_table]:text-text-primary [&_th]:border [&_th]:border-border-default [&_th]:px-2 [&_th]:py-1",
                  "[&_td]:border [&_td]:border-border-default [&_td]:px-2 [&_td]:py-1",
                ].join(" ")}
                title="点击编辑"
              >
                {content.trim() ? (
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {content}
                  </ReactMarkdown>
                ) : (
                  <span className="text-text-muted italic text-xs">
                    {`点击输入${label}…`}
                  </span>
                )}
              </div>
            )}
          </>
        )}
      </section>
    );
  }
);
