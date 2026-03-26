// src/store/llm.ts
// LLM 流式任务状态管理。
// 各任务独立存储 token 列表，支持逐字追加渲染。

import { create } from "zustand";

export type LlmTaskStatus =
  | "pending"
  | "running"
  | "done"
  | "failed"
  | "cancelled";

export interface LlmTaskState {
  taskId: string;
  documentId: string;
  status: LlmTaskStatus;
  tokens: string[];          // 流式 token 列表（逐个追加）
  resultText: string | null; // done 后的完整文本（来自 llm:done 事件）
  errorMsg: string | null;
}

function createPlaceholderTask(taskId: string): LlmTaskState {
  return {
    taskId,
    documentId: "",
    status: "pending",
    tokens: [],
    resultText: null,
    errorMsg: null,
  };
}

function updateTask(
  tasks: Map<string, LlmTaskState>,
  taskId: string,
  updater: (task: LlmTaskState) => LlmTaskState,
): Map<string, LlmTaskState> {
  const next = new Map(tasks);
  const current = next.get(taskId) ?? createPlaceholderTask(taskId);
  next.set(taskId, updater(current));
  return next;
}

interface LlmStore {
  tasks: Map<string, LlmTaskState>;

  initTask: (taskId: string, documentId: string) => void;
  appendToken: (taskId: string, token: string) => void;
  setDone: (taskId: string, resultText: string) => void;
  setError: (taskId: string, error: string) => void;
  setCancelled: (taskId: string) => void;
  getDocumentTasks: (documentId: string) => LlmTaskState[];
  clearFinished: (documentId: string) => void;
}

export const useLlmStore = create<LlmStore>((set, get) => ({
  tasks: new Map(),

  initTask: (taskId, documentId) =>
    set((s) => {
      return {
        tasks: updateTask(s.tasks, taskId, (task) => ({
          ...task,
          documentId,
        })),
      };
    }),

  appendToken: (taskId, token) =>
    set((s) => {
      return {
        tasks: updateTask(s.tasks, taskId, (task) => ({
          ...task,
          status: "running",
          tokens: [...task.tokens, token],
        })),
      };
    }),

  setDone: (taskId, resultText) =>
    set((s) => {
      return {
        tasks: updateTask(s.tasks, taskId, (task) => ({
          ...task,
          status: "done",
          resultText,
          errorMsg: null,
        })),
      };
    }),

  setError: (taskId, error) =>
    set((s) => {
      return {
        tasks: updateTask(s.tasks, taskId, (task) => ({
          ...task,
          status: "failed",
          errorMsg: error,
        })),
      };
    }),

  setCancelled: (taskId) =>
    set((s) => {
      return {
        tasks: updateTask(s.tasks, taskId, (task) => ({
          ...task,
          status: "cancelled",
        })),
      };
    }),

  getDocumentTasks: (documentId) => {
    const all = Array.from(get().tasks.values());
    return all.filter((t) => t.documentId === documentId);
  },

  clearFinished: (documentId) =>
    set((s) => {
      const next = new Map(s.tasks);
      for (const [id, task] of next) {
        if (
          task.documentId === documentId &&
          (task.status === "done" ||
            task.status === "failed" ||
            task.status === "cancelled")
        ) {
          next.delete(id);
        }
      }
      return { tasks: next };
    }),
}));
