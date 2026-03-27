import { useEffect } from "react";
import { useNavigate } from "@tanstack/react-router";
import {
  AlertCircle,
  CheckCircle2,
  Clock3,
  Loader2,
  X,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import {
  useTranscriptionStore,
  type BatchJobStatus,
  type BatchStatus,
} from "@/store/transcription";

function StatusBadge({ status }: { status: BatchStatus }) {
  switch (status.type) {
    case "Queued":
      return (
        <Badge variant="outline" className="gap-1 border-border-default text-text-muted">
          <Clock3 className="h-3 w-3" />
          排队中
        </Badge>
      );
    case "Processing":
      return (
        <Badge variant="outline" className="gap-1 border-blue-400/30 text-blue-300">
          <Loader2 className="h-3 w-3 animate-spin" />
          转写中
        </Badge>
      );
    case "Done":
      return (
        <Badge variant="outline" className="gap-1 border-emerald-400/30 text-emerald-300">
          <CheckCircle2 className="h-3 w-3" />
          完成
        </Badge>
      );
    case "Failed":
      return (
        <Badge variant="outline" className="gap-1 border-red-400/30 text-red-300">
          <AlertCircle className="h-3 w-3" />
          失败
        </Badge>
      );
    case "Cancelled":
      return (
        <Badge variant="outline" className="border-border-default text-text-muted">
          已取消
        </Badge>
      );
  }
}

function JobRow({
  job,
  onCancel,
}: {
  job: BatchJobStatus;
  onCancel: (jobId: string) => void;
}) {
  const navigate = useNavigate();
  const canCancel =
    job.status.type === "Queued" || job.status.type === "Processing";
  const progress =
    job.status.type === "Processing" ? job.status.data.progress * 100 : null;

  const handleOpen = () => {
    if (job.status.type !== "Done") {
      return;
    }

    void navigate({
      to: "/workspace/document/$documentId",
      params: { documentId: job.status.data.document_id },
    });
  };

  return (
    <div
      className={[
        "group rounded-xl border border-border-default bg-bg-secondary/60 p-4 transition-colors",
        job.status.type === "Done" ? "cursor-pointer hover:bg-bg-secondary" : "",
      ].join(" ")}
      onClick={handleOpen}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 space-y-1">
          <p className="truncate text-sm font-medium text-text-primary" title={job.file_name}>
            {job.file_name}
          </p>
          <p className="text-[11px] text-text-muted">
            {new Date(job.created_at).toLocaleString()}
          </p>
        </div>

        <div className="flex shrink-0 items-center gap-2">
          <StatusBadge status={job.status} />
          {canCancel ? (
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7 opacity-0 transition-opacity group-hover:opacity-100"
              onClick={(event) => {
                event.stopPropagation();
                onCancel(job.job_id);
              }}
            >
              <X className="h-4 w-4" />
            </Button>
          ) : null}
        </div>
      </div>

      {progress !== null ? (
        <div className="mt-3 space-y-1.5">
          <Progress value={progress} className="h-1.5" />
          <p className="text-[11px] text-text-muted">{Math.round(progress)}%</p>
        </div>
      ) : null}

      {job.status.type === "Failed" ? (
        <p className="mt-3 text-xs leading-5 text-red-300">
          {job.status.data.error}
        </p>
      ) : null}
    </div>
  );
}

export function TranscriptionMain() {
  const queue = useTranscriptionStore((state) => state.queue ?? []);
  const cancelJob = useTranscriptionStore((state) => state.cancelJob);
  const clearCompleted = useTranscriptionStore((state) => state.clearCompleted);
  const refreshQueue = useTranscriptionStore((state) => state.refreshQueue);
  const setupEventListeners = useTranscriptionStore(
    (state) => state.setupEventListeners,
  );

  useEffect(() => {
    void refreshQueue();

    let cleanup: (() => void) | undefined;
    void setupEventListeners().then((dispose) => {
      cleanup = dispose;
    });

    return () => {
      cleanup?.();
    };
  }, [refreshQueue, setupEventListeners]);

  const hasCompleted = queue.some(
    (job) =>
      job.status.type === "Done" ||
      job.status.type === "Failed" ||
      job.status.type === "Cancelled",
  );

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-border-default px-4 py-3">
        <div>
          <h2 className="text-sm font-medium text-text-primary">转写队列</h2>
          <p className="text-xs text-text-muted">
            {queue.length > 0 ? `当前共 ${queue.length} 个任务` : "等待新的批量转写任务"}
          </p>
        </div>

        {hasCompleted ? (
          <Button variant="ghost" size="sm" onClick={() => void clearCompleted()}>
            清除已完成
          </Button>
        ) : null}
      </div>

      <div className="flex-1 space-y-3 overflow-y-auto p-4">
        {queue.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center rounded-2xl border border-dashed border-border-default text-center">
            <p className="text-sm font-medium text-text-primary">暂无转写任务</p>
            <p className="mt-2 text-xs text-text-muted">
              从左侧拖入音频或视频文件，队列会自动开始处理。
            </p>
          </div>
        ) : (
          queue.map((job) => (
            <JobRow
              key={job.job_id}
              job={job}
              onCancel={(jobId) => void cancelJob(jobId)}
            />
          ))
        )}
      </div>
    </div>
  );
}
