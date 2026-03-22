// src/components/workspace/AiPanel.tsx
// "✨ AI 工具" Popover panel:
//   - 生成摘要 / 会议纪要 / 翻译 buttons
//   - Streaming preview via StreamingText
//   - 插入到光标位置 button (requires onInsertAtCursor prop)
//   - Cancel while running

import { useState } from "react";
import * as Popover from "@radix-ui/react-popover";
import { Sparkles, FileText, Users, Languages, X, Loader2, ArrowDownToLine, ChevronDown } from "lucide-react";
import { commands } from "@/lib/bindings";
import { useLlmStore } from "@/store/llm";
import { StreamingText } from "@/components/ui/StreamingText";

const TRANSLATION_LANGUAGES = [
  { value: "en",  label: "英文" },
  { value: "ja",  label: "日文" },
  { value: "ko",  label: "韩文" },
  { value: "fr",  label: "法文" },
  { value: "de",  label: "德文" },
  { value: "es",  label: "西班牙文" },
  { value: "ru",  label: "俄文" },
] as const;

type TaskKind = "summary" | "meeting_brief" | "translation";

interface AiPanelProps {
  documentId: string;
  /** If provided, shows "插入到光标位置" button after generation. */
  onInsertAtCursor?: (text: string) => void;
}

export function AiPanel({ documentId, onInsertAtCursor }: AiPanelProps) {
  const { tasks, initTask } = useLlmStore();

  const [activeTaskId, setActiveTaskId] = useState<string | null>(null);
  const [targetLang, setTargetLang] = useState<string>("en");
  const [showLangMenu, setShowLangMenu] = useState(false);

  const activeTask = activeTaskId ? tasks.get(activeTaskId) : null;
  const isRunning =
    activeTask?.status === "pending" || activeTask?.status === "running";
  const isDone =
    activeTask?.status === "done" ||
    activeTask?.status === "failed" ||
    activeTask?.status === "cancelled";

  const handleSubmit = async (kind: TaskKind) => {
    if (isRunning) return;

    const taskType =
      kind === "translation"
        ? ({ type: "translation", data: { target_language: targetLang } } as const)
        : kind === "meeting_brief"
          ? ({ type: "meeting_brief" } as const)
          : ({ type: "summary" } as const);

    try {
      const result = await commands.submitLlmTask({
        document_id: documentId,
        task_type: taskType,
        text_role_hint: null,
      });
      if (result.status === "error") throw new Error(String(result.error));
      const taskId = result.data;
      initTask(taskId, documentId);
      setActiveTaskId(taskId);
    } catch (err) {
      console.error("[AiPanel] submit error:", err);
    }
  };

  const handleCancel = async () => {
    if (!activeTaskId) return;
    try {
      await commands.cancelLlmTask(activeTaskId);
    } catch (err) {
      console.error("[AiPanel] cancel error:", err);
    }
  };

  const targetLangLabel =
    TRANSLATION_LANGUAGES.find((l) => l.value === targetLang)?.label ?? "英文";

  return (
    <Popover.Root>
      <Popover.Trigger asChild>
        <button
          className={[
            "flex items-center gap-1 px-2 py-1 rounded text-xs font-medium",
            "border border-border-default text-text-secondary",
            "hover:bg-bg-tertiary hover:text-text-primary transition-colors",
          ].join(" ")}
          title="AI 工具"
        >
          <Sparkles className="w-3.5 h-3.5" />
          AI 工具
        </button>
      </Popover.Trigger>

      <Popover.Portal>
        <Popover.Content
          side="bottom"
          align="end"
          sideOffset={6}
          className={[
            "z-50 w-80 rounded-lg border border-border-default bg-bg-primary shadow-xl p-3",
          ].join(" ")}
        >
          {/* Action buttons */}
          <div className="flex flex-col gap-1 mb-3">
            <button
              disabled={isRunning}
              onClick={() => handleSubmit("summary")}
              className="flex items-center gap-2 px-3 py-2 rounded text-sm text-text-primary hover:bg-bg-tertiary disabled:opacity-50 disabled:cursor-not-allowed transition-colors text-left"
            >
              <FileText className="w-3.5 h-3.5 text-text-secondary shrink-0" />
              生成摘要
            </button>

            <button
              disabled={isRunning}
              onClick={() => handleSubmit("meeting_brief")}
              className="flex items-center gap-2 px-3 py-2 rounded text-sm text-text-primary hover:bg-bg-tertiary disabled:opacity-50 disabled:cursor-not-allowed transition-colors text-left"
            >
              <Users className="w-3.5 h-3.5 text-text-secondary shrink-0" />
              会议纪要
            </button>

            {/* Translation row with language picker */}
            <div className="flex items-center gap-1">
              <button
                disabled={isRunning}
                onClick={() => handleSubmit("translation")}
                className="flex flex-1 items-center gap-2 px-3 py-2 rounded text-sm text-text-primary hover:bg-bg-tertiary disabled:opacity-50 disabled:cursor-not-allowed transition-colors text-left"
              >
                <Languages className="w-3.5 h-3.5 text-text-secondary shrink-0" />
                翻译为 {targetLangLabel}
              </button>

              {/* Language selector */}
              <div className="relative">
                <button
                  onClick={() => setShowLangMenu((v) => !v)}
                  className="flex items-center gap-0.5 px-2 py-1.5 rounded text-xs text-text-muted hover:bg-bg-tertiary transition-colors"
                  title="选择语言"
                >
                  <ChevronDown className="w-3 h-3" />
                </button>
                {showLangMenu && (
                  <div className="absolute right-0 top-full mt-1 z-10 min-w-[100px] rounded-md border border-border-default bg-bg-primary shadow-lg py-1">
                    {TRANSLATION_LANGUAGES.map((lang) => (
                      <button
                        key={lang.value}
                        onClick={() => {
                          setTargetLang(lang.value);
                          setShowLangMenu(false);
                        }}
                        className={[
                          "w-full text-left px-3 py-1.5 text-xs hover:bg-bg-tertiary transition-colors",
                          lang.value === targetLang
                            ? "text-accent-primary font-medium"
                            : "text-text-primary",
                        ].join(" ")}
                      >
                        {lang.label}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Running indicator */}
          {isRunning && (
            <div className="flex items-center justify-between mb-2">
              <span className="flex items-center gap-1.5 text-xs text-text-muted">
                <Loader2 className="w-3 h-3 animate-spin" />
                AI 处理中…
              </span>
              <button
                onClick={handleCancel}
                className="flex items-center gap-1 text-xs text-status-error hover:opacity-80 transition-opacity"
              >
                <X className="w-3 h-3" />
                取消
              </button>
            </div>
          )}

          {/* Streaming preview */}
          {activeTask && activeTask.tokens.length > 0 && (
            <div className="rounded-md border border-border-default bg-bg-secondary p-3 mb-2 max-h-48 overflow-y-auto">
              <StreamingText
                tokens={activeTask.tokens}
                isFinished={isDone}
              />
              {activeTask.status === "failed" && activeTask.errorMsg && (
                <p className="mt-2 text-xs text-status-error">
                  错误：{activeTask.errorMsg}
                </p>
              )}
            </div>
          )}

          {/* Insert at cursor button */}
          {isDone && activeTask?.resultText && onInsertAtCursor && (
            <button
              onClick={() => onInsertAtCursor(activeTask.resultText!)}
              className="flex items-center gap-1.5 w-full justify-end text-xs text-accent-primary hover:opacity-80 transition-opacity"
            >
              <ArrowDownToLine className="w-3 h-3" />
              插入到光标位置
            </button>
          )}

          <Popover.Arrow className="fill-border-default" />
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}
