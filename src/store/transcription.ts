import { create } from "zustand";
import { listen, type UnlistenFn } from "@tauri-apps/api/event";
import { invoke } from "@tauri-apps/api/core";
import { commands } from "@/lib/bindings";

type CommandResult<T> =
  | { status: "ok"; data: T }
  | { status: "error"; error: unknown };

export type BatchStatus =
  | { type: "Queued" }
  | { type: "Processing"; data: { progress: number } }
  | { type: "Done"; data: { recording_id: string; document_id: string } }
  | { type: "Failed"; data: { error: string } }
  | { type: "Cancelled" };

export interface BatchJobStatus {
  job_id: string;
  file_name: string;
  language: string | null;
  status: BatchStatus;
  created_at: number;
}

type BatchCommandBindings = typeof commands & {
  checkFfmpegAvailable: () => Promise<CommandResult<boolean>>;
  addFilesToBatch: (paths: string[]) => Promise<CommandResult<string[]>>;
  getBatchQueue: () => Promise<CommandResult<BatchJobStatus[]>>;
  cancelBatchJob: (jobId: string) => Promise<CommandResult<null>>;
  clearCompletedJobs: () => Promise<CommandResult<null>>;
};

const batchCommands = commands as BatchCommandBindings;

function withInvoke<T>(command: string, args?: Record<string, unknown>) {
  return async (): Promise<CommandResult<T>> => {
    try {
      return { status: "ok", data: await invoke<T>(command, args) };
    } catch (error) {
      if (error instanceof Error) throw error;
      return { status: "error", error };
    }
  };
}

function ensureBatchBindings() {
  const commandMap = batchCommands as Record<string, unknown>;

  if (typeof commandMap.checkFfmpegAvailable !== "function") {
    batchCommands.checkFfmpegAvailable = withInvoke<boolean>(
      "check_ffmpeg_available",
    );
  }

  if (typeof commandMap.addFilesToBatch !== "function") {
    batchCommands.addFilesToBatch = (paths: string[]) =>
      withInvoke<string[]>("add_files_to_batch", { paths })();
  }

  if (typeof commandMap.getBatchQueue !== "function") {
    batchCommands.getBatchQueue = withInvoke<BatchJobStatus[]>("get_batch_queue");
  }

  if (typeof commandMap.cancelBatchJob !== "function") {
    batchCommands.cancelBatchJob = (jobId: string) =>
      withInvoke<null>("cancel_batch_job", { jobId })();
  }

  if (typeof commandMap.clearCompletedJobs !== "function") {
    batchCommands.clearCompletedJobs = withInvoke<null>("clear_completed_jobs");
  }
}

function upsertQueueJob(
  queue: BatchJobStatus[],
  nextJob: BatchJobStatus,
): BatchJobStatus[] {
  const index = queue.findIndex((job) => job.job_id === nextJob.job_id);
  if (index === -1) {
    return [...queue, nextJob];
  }

  const nextQueue = [...queue];
  nextQueue[index] = nextJob;
  return nextQueue;
}

interface TranscriptionStore {
  queue: BatchJobStatus[];
  ffmpegAvailable: boolean;
  isCheckingFfmpeg: boolean;
  _unlisteners: UnlistenFn[];

  checkFfmpeg: () => Promise<void>;
  addFiles: (paths: string[]) => Promise<string[]>;
  cancelJob: (jobId: string) => Promise<void>;
  clearCompleted: () => Promise<void>;
  refreshQueue: () => Promise<void>;
  setupEventListeners: () => Promise<() => void>;
}

ensureBatchBindings();

export const useTranscriptionStore = create<TranscriptionStore>((set, get) => ({
  queue: [],
  ffmpegAvailable: true,
  isCheckingFfmpeg: false,
  _unlisteners: [],

  checkFfmpeg: async () => {
    set({ isCheckingFfmpeg: true });
    try {
      const result = await batchCommands.checkFfmpegAvailable();
      if (result.status === "ok") {
        set({ ffmpegAvailable: result.data });
      }
    } finally {
      set({ isCheckingFfmpeg: false });
    }
  },

  addFiles: async (paths) => {
    const result = await batchCommands.addFilesToBatch(paths);
    if (result.status === "error") {
      throw new Error(String(result.error));
    }

    await get().refreshQueue();
    return result.data;
  },

  cancelJob: async (jobId) => {
    const result = await batchCommands.cancelBatchJob(jobId);
    if (result.status === "error") {
      throw new Error(String(result.error));
    }

    set((state) => ({
      queue: state.queue.map((job) =>
        job.job_id === jobId
          ? { ...job, status: { type: "Cancelled" as const } }
          : job,
      ),
    }));
  },

  clearCompleted: async () => {
    const result = await batchCommands.clearCompletedJobs();
    if (result.status === "error") {
      throw new Error(String(result.error));
    }

    set((state) => ({
      queue: state.queue.filter(
        (job) =>
          job.status.type !== "Done" &&
          job.status.type !== "Failed" &&
          job.status.type !== "Cancelled",
      ),
    }));
  },

  refreshQueue: async () => {
    const result = await batchCommands.getBatchQueue();
    if (result.status === "ok") {
      set({ queue: result.data });
    }
  },

  setupEventListeners: async () => {
    get()._unlisteners.forEach((unlisten) => unlisten());

    const unlisteners = await Promise.all([
      listen<{ job_id: string; file_name: string }>("batch:queued", (event) => {
        const { job_id, file_name } = event.payload;
        set((state) => ({
          queue: upsertQueueJob(state.queue, {
            job_id,
            file_name,
            language: null,
            status: { type: "Queued" },
            created_at: Date.now(),
          }),
        }));
      }),

      listen<{ job_id: string; file_name: string; progress: number }>(
        "batch:progress",
        (event) => {
          const { job_id, file_name, progress } = event.payload;
          set((state) => ({
            queue: upsertQueueJob(state.queue, {
              job_id,
              file_name,
              language:
                state.queue.find((job) => job.job_id === job_id)?.language ?? null,
              created_at:
                state.queue.find((job) => job.job_id === job_id)?.created_at ??
                Date.now(),
              status: { type: "Processing", data: { progress } },
            }),
          }));
        },
      ),

      listen<{ job_id: string; recording_id: string; document_id: string }>(
        "batch:done",
        (event) => {
          const { job_id, recording_id, document_id } = event.payload;
          set((state) => ({
            queue: state.queue.map((job) =>
              job.job_id === job_id
                ? {
                    ...job,
                    status: {
                      type: "Done",
                      data: { recording_id, document_id },
                    },
                  }
                : job,
            ),
          }));
        },
      ),

      listen<{ job_id: string; file_name: string; error: string }>(
        "batch:error",
        (event) => {
          const { job_id, file_name, error } = event.payload;
          set((state) => ({
            queue: upsertQueueJob(
              state.queue.map((job) =>
                job.job_id === job_id
                  ? { ...job, status: { type: "Failed", data: { error } } }
                  : job,
              ),
              {
                job_id,
                file_name,
                language: null,
                created_at: Date.now(),
                status: { type: "Failed", data: { error } },
              },
            ),
          }));
        },
      ),

      listen("batch:ffmpeg_missing", () => {
        set({ ffmpegAvailable: false });
      }),
    ]);

    set({ _unlisteners: unlisteners });

    return () => {
      unlisteners.forEach((unlisten) => unlisten());
      set({ _unlisteners: [] });
    };
  },
}));
