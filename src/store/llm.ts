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
      const next = new Map(s.tasks);
      next.set(taskId, {
        taskId,
        documentId,
        status: "pending",
        tokens: [],
        resultText: null,
        errorMsg: null,
      });
      return { tasks: next };
    }),

  appendToken: (taskId, token) =>
    set((s) => {
      const task = s.tasks.get(taskId);
      if (!task) return s;
      const next = new Map(s.tasks);
      next.set(taskId, {
        ...task,
        status: "running",
        tokens: [...task.tokens, token],
      });
      return { tasks: next };
    }),

  setDone: (taskId, resultText) =>
    set((s) => {
      const task = s.tasks.get(taskId);
      if (!task) return s;
      const next = new Map(s.tasks);
      next.set(taskId, { ...task, status: "done", resultText });
      return { tasks: next };
    }),

  setError: (taskId, error) =>
    set((s) => {
      const task = s.tasks.get(taskId);
      if (!task) return s;
      const next = new Map(s.tasks);
      next.set(taskId, { ...task, status: "failed", errorMsg: error });
      return { tasks: next };
    }),

  setCancelled: (taskId) =>
    set((s) => {
      const task = s.tasks.get(taskId);
      if (!task) return s;
      const next = new Map(s.tasks);
      next.set(taskId, { ...task, status: "cancelled" });
      return { tasks: next };
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
