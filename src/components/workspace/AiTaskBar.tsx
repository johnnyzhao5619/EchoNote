// src/components/workspace/AiTaskBar.tsx
// AI 操作区：生成摘要、会议纪要、翻译三个按钮，含加载状态和取消按钮。

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Loader2, X, FileText, Users, Languages } from "lucide-react";
import { invoke } from "@tauri-apps/api/core";
import { useLlmStore } from "@/store/llm";
import { StreamingText } from "@/components/ui/StreamingText";

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
          ? { Translation: { target_language: targetLanguage } }
          : kind === "meeting_brief"
            ? { MeetingBrief: null }
            : { Summary: null };

      const taskId = await invoke<string>("submit_llm_task", {
        request: {
          document_id: documentId,
          task_type: taskType,
          text_role_hint: null,
        },
      });

      initTask(taskId, documentId);
      setActiveTaskId(taskId);
    } catch (err) {
      console.error("[AiTaskBar] submit error:", err);
    }
  };

  const handleCancel = async () => {
    if (!activeTaskId) return;
    try {
      await invoke("cancel_llm_task", { taskId: activeTaskId });
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
      </div>

      {/* 流式输出区域 */}
      {activeTask && activeTask.tokens.length > 0 && (
        <div className="rounded-md border border-border bg-bg-secondary p-3">
          <StreamingText
            tokens={activeTask.tokens}
            isFinished={
              activeTask.status === "done" ||
              activeTask.status === "failed" ||
              activeTask.status === "cancelled"
            }
          />
          {activeTask.status === "failed" && activeTask.errorMsg && (
            <p className="mt-2 text-xs text-status-error">
              错误：{activeTask.errorMsg}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
