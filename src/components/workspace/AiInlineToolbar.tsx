// src/components/workspace/AiInlineToolbar.tsx
// Floating toolbar that appears above a textarea selection.
// Uses `textarea-caret` to compute pixel position of the selection start.
// Currently exposes: Copy.  Future: translate / summarize selected text.

import { useState, useEffect, useCallback } from "react";
import { createPortal } from "react-dom";
import { Copy, Check } from "lucide-react";
import getCaretCoordinates from "textarea-caret";

interface Position {
  top: number;
  left: number;
}

interface AiInlineToolbarProps {
  textareaRef: React.RefObject<HTMLTextAreaElement | null>;
}

function getToolbarPosition(el: HTMLTextAreaElement): Position | null {
  const { selectionStart, selectionEnd } = el;
  if (selectionStart === selectionEnd) return null;

  const caret = getCaretCoordinates(el, selectionStart);
  const rect = el.getBoundingClientRect();

  const toolbarHeight = 36;
  const rawTop = rect.top + caret.top - el.scrollTop - toolbarHeight - 6;
  const rawLeft = rect.left + caret.left;

  // If too close to top of viewport, display below selection instead
  const top =
    rawTop < 4
      ? rect.top + caret.top - el.scrollTop + (caret.height ?? 18) + 4
      : rawTop;

  // Clamp left so toolbar stays inside viewport
  const maxLeft = window.innerWidth - 120;
  const left = Math.min(Math.max(rawLeft, 4), maxLeft);

  return { top, left };
}

export function AiInlineToolbar({ textareaRef }: AiInlineToolbarProps) {
  const [position, setPosition] = useState<Position | null>(null);
  const [selectedText, setSelectedText] = useState("");
  const [copied, setCopied] = useState(false);

  const update = useCallback(() => {
    const el = textareaRef.current;
    if (!el) { setPosition(null); return; }
    const pos = getToolbarPosition(el);
    setPosition(pos);
    if (pos) {
      setSelectedText(el.value.slice(el.selectionStart, el.selectionEnd));
    }
  }, [textareaRef]);

  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;

    el.addEventListener("mouseup", update);
    el.addEventListener("keyup", update);
    el.addEventListener("blur", () => setPosition(null));

    return () => {
      el.removeEventListener("mouseup", update);
      el.removeEventListener("keyup", update);
      el.removeEventListener("blur", () => setPosition(null));
    };
  }, [textareaRef, update]);

  const handleCopy = async () => {
    if (!selectedText) return;
    await navigator.clipboard.writeText(selectedText);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  if (!position) return null;

  return createPortal(
    <div
      style={{ top: position.top, left: position.left }}
      className={[
        "fixed z-[60] flex items-center gap-0.5",
        "rounded-md border border-border-default bg-bg-primary shadow-lg px-1 py-0.5",
        "pointer-events-auto select-none",
      ].join(" ")}
      // Prevent mousedown from blurring the textarea (which hides the toolbar)
      onMouseDown={(e) => e.preventDefault()}
    >
      <button
        onClick={handleCopy}
        className="flex items-center gap-1 px-2 py-1 rounded text-xs text-text-secondary hover:bg-bg-tertiary hover:text-text-primary transition-colors"
        title="复制选中文本"
      >
        {copied ? (
          <Check className="w-3 h-3 text-status-success" />
        ) : (
          <Copy className="w-3 h-3" />
        )}
        {copied ? "已复制" : "复制"}
      </button>
    </div>,
    document.body
  );
}
