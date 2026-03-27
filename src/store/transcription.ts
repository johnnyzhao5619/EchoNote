import { create } from "zustand";
import { listen, type UnlistenFn } from "@tauri-apps/api/event";
import { commands } from "@/lib/bindings";

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

function unwrapResult<T>(
  result: { status: "ok"; data: T } | { status: "error"; error: unknown },
  action: string,
): T {
  if (result.status === "error") {
    throw new Error(`${action}: ${String(result.error)}`);
  }
  return result.data;
}

export const useTranscriptionStore = create<TranscriptionStore>((set, get) => ({
  queue: [],
  ffmpegAvailable: true,
  isCheckingFfmpeg: false,
  _unlisteners: [],

  checkFfmpeg: async () => {
    set({ isCheckingFfmpeg: true });
    try {
      const ffmpegAvailable = await commands.checkFfmpegAvailable();
      set({ ffmpegAvailable });
    } finally {
      set({ isCheckingFfmpeg: false });
    }
  },

  addFiles: async (paths) => {
    const result = await commands.addFilesToBatch(paths);
    await get().refreshQueue();
    return unwrapResult(result, "addFilesToBatch");
  },

  cancelJob: async (jobId) => {
    unwrapResult(await commands.cancelBatchJob(jobId), "cancelBatchJob");

    set((state) => ({
      queue: state.queue.map((job) =>
        job.job_id === jobId
          ? { ...job, status: { type: "Cancelled" as const } }
          : job,
      ),
    }));
  },

  clearCompleted: async () => {
    unwrapResult(
      await commands.clearCompletedJobs(),
      "clearCompletedJobs",
    );

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
    const result = await commands.getBatchQueue();
    if (result.status === "ok" && Array.isArray(result.data)) {
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
