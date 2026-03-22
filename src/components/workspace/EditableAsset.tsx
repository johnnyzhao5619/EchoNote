// src/components/workspace/EditableAsset.tsx
// Collapsible, editable section for one text asset with debounced autosave.

import { useState, useEffect, useRef, useCallback } from "react";
import { commands } from "@/lib/bindings";
import { ChevronDown, ChevronRight, Check, Loader2 } from "lucide-react";

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
  const [open, setOpen] = useState(true);
  const [content, setContent] = useState(initialContent);
  const [saveState, setSaveState] = useState<SaveState>("idle");
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastSavedRef = useRef(initialContent);

  // Keep content in sync if parent reloads (e.g., AI task completes)
  useEffect(() => {
    // Only update if user hasn't made local changes
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

    // Debounce: save 1.5s after user stops typing
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => save(text), 1500);
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
      </div>

      {/* Editable textarea */}
      {open && (
        <textarea
          value={content}
          onChange={handleChange}
          className={[
            "w-full min-h-[120px] text-sm text-text-primary leading-relaxed",
            "rounded-md bg-bg-secondary border border-border-default p-3",
            "resize-y focus:outline-none focus:ring-1 focus:ring-accent-primary",
            "placeholder:text-text-muted font-mono",
          ].join(" ")}
          placeholder={`在此输入${label}…`}
          spellCheck={false}
        />
      )}
    </section>
  );
}
