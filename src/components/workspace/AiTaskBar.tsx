// src/components/workspace/AiTaskBar.tsx
// AI 操作区：生成摘要、会议纪要、翻译三个按钮，含加载状态和取消按钮。

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Loader2, X, FileText, Users, Languages } from "lucide-react";
import { commands } from "@/lib/bindings";
import { useLlmStore } from "@/store/llm";

interface AiTaskBarProps {
  documentId: string;
  /** 目标翻译语言，默认 "English" */
  targetLanguage?: string;
}

type TaskKind = "summary" | "meeting_brief" | "translation";

export function AiTaskBar({
  documentId,
  targetLanguage = "English",
}: AiTaskBarProps) {
  const { tasks, initTask } = useLlmStore();
  const [activeTaskId, setActiveTaskId] = useState<string | null>(null);

  const activeTask = activeTaskId ? tasks.get(activeTaskId) : null;
  const isRunning =
    activeTask?.status === "pending" || activeTask?.status === "running";

  const handleSubmit = async (kind: TaskKind) => {
    if (isRunning) return;

    try {
      const taskType =
        kind === "translation"
          ? ({ type: "translation", data: { target_language: targetLanguage } } as const)
          : kind === "meeting_brief"
            ? ({ type: "meeting_brief" } as const)
            : ({ type: "summary" } as const);

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
      console.error("[AiTaskBar] submit error:", err);
    }
  };

  const handleCancel = async () => {
    if (!activeTaskId) return;
    try {
      const result = await commands.cancelLlmTask(activeTaskId);
      if (result.status === "error") throw new Error(String(result.error));
    } catch (err) {
      console.error("[AiTaskBar] cancel error:", err);
    }
  };

  return (
    <div className="flex flex-col gap-3">
      {/* 操作按钮行 */}
      <div className="flex items-center gap-2 flex-wrap">
        <Button
          variant="outline"
          size="sm"
          disabled={isRunning}
          onClick={() => handleSubmit("summary")}
          className="gap-1.5"
        >
          <FileText className="w-3.5 h-3.5" />
          生成摘要
        </Button>

        <Button
          variant="outline"
          size="sm"
          disabled={isRunning}
          onClick={() => handleSubmit("meeting_brief")}
          className="gap-1.5"
        >
          <Users className="w-3.5 h-3.5" />
          会议纪要
        </Button>

        <Button
          variant="outline"
          size="sm"
          disabled={isRunning}
          onClick={() => handleSubmit("translation")}
          className="gap-1.5"
        >
          <Languages className="w-3.5 h-3.5" />
          翻译为 {targetLanguage}
        </Button>

        {isRunning && (
          <Button
            variant="ghost"
            size="sm"
            onClick={handleCancel}
            className="gap-1.5 text-status-error hover:text-status-error"
          >
            <X className="w-3.5 h-3.5" />
            取消
          </Button>
        )}

        {isRunning && (
          <span className="flex items-center gap-1.5 text-xs text-text-muted ml-auto">
            <Loader2 className="w-3 h-3 animate-spin" />
            AI 处理中…
          </span>
        )}

        {activeTask?.status === "failed" && activeTask.errorMsg && (
          <span className="flex items-center gap-1.5 text-xs text-status-error ml-auto">
            错误：{activeTask.errorMsg}
          </span>
        )}
      </div>
    </div>
  );
}
