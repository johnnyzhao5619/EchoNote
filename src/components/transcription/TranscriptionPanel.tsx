import { useCallback } from "react";
import { open } from "@tauri-apps/plugin-dialog";
import { useDropzone } from "react-dropzone";
import { FileAudio, Upload } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useTranscriptionStore } from "@/store/transcription";
import { FfmpegWarning } from "./FfmpegWarning";

const SUPPORTED_EXTENSIONS = [
  ".wav",
  ".flac",
  ".mp3",
  ".mp4",
  ".m4a",
  ".mov",
  ".mkv",
  ".webm",
  ".ogg",
];

const DIRECT_FORMATS = ["WAV"];
const TRANSCODE_FORMATS = ["FLAC", "MP3", "MP4", "M4A", "MOV", "MKV", "WEBM", "OGG"];

function getFilePaths(files: File[]) {
  return files
    .map((file) => {
      const candidate = file as File & { path?: string };
      return candidate.path ?? "";
    })
    .filter(Boolean);
}

export function TranscriptionPanel() {
  const addFiles = useTranscriptionStore((state) => state.addFiles);
  const ffmpegAvailable = useTranscriptionStore((state) => state.ffmpegAvailable);

  const handleFiles = useCallback(
    async (filePaths: string[]) => {
      if (filePaths.length === 0) {
        return;
      }

      try {
        await addFiles(filePaths);
      } catch (error) {
        console.error("[transcription] addFiles failed:", error);
      }
    },
    [addFiles],
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    accept: {
      "audio/*": SUPPORTED_EXTENSIONS,
      "video/*": [".mp4", ".mov", ".mkv", ".webm", ".m4a"],
    },
    noClick: true,
    onDrop: (acceptedFiles) => {
      void handleFiles(getFilePaths(acceptedFiles));
    },
  });

  const openFileDialog = async () => {
    const selected = await open({
      multiple: true,
      filters: [
        {
          name: "音频/视频文件",
          extensions: ["wav", "flac", "mp3", "mp4", "m4a", "mov", "mkv", "webm", "ogg"],
        },
      ],
    });

    if (!selected) {
      return;
    }

    const paths = Array.isArray(selected) ? selected : [selected];
    await handleFiles(paths);
  };

  return (
    <div className="flex h-full flex-col gap-4 overflow-y-auto p-4">
      {!ffmpegAvailable ? <FfmpegWarning /> : null}

      <div
        {...getRootProps()}
        className={[
          "rounded-2xl border border-dashed p-6 transition-colors",
          "flex min-h-56 flex-col items-center justify-center gap-3 text-center",
          isDragActive
            ? "border-accent bg-bg-secondary"
            : "border-border-default bg-bg-secondary/60 hover:border-accent/60 hover:bg-bg-secondary",
        ].join(" ")}
      >
        <input {...getInputProps()} />
        <div className="rounded-full border border-border-default bg-bg-primary p-3">
          <Upload className="h-6 w-6 text-text-secondary" />
        </div>

        <div className="space-y-1">
          <p className="text-sm font-medium text-text-primary">
            {isDragActive ? "松开以添加媒体文件" : "拖拽媒体文件到这里"}
          </p>
          <p className="text-xs text-text-muted">
            支持批量添加，队列会按顺序逐个转写。
          </p>
        </div>

        <Button variant="outline" size="sm" onClick={() => void openFileDialog()}>
          <FileAudio className="h-4 w-4" />
          选择文件
        </Button>
      </div>

      <div className="space-y-2 rounded-xl border border-border-default bg-bg-secondary/40 p-4">
        <p className="text-xs font-semibold uppercase tracking-wide text-text-secondary">
          支持格式
        </p>

        <div className="flex flex-wrap gap-2">
          {DIRECT_FORMATS.map((format) => (
            <span
              key={format}
              className="rounded-full bg-emerald-500/15 px-2.5 py-1 text-[11px] font-medium text-emerald-300"
            >
              {format}
            </span>
          ))}

          {TRANSCODE_FORMATS.map((format) => (
            <span
              key={format}
              className="rounded-full bg-bg-primary px-2.5 py-1 text-[11px] font-medium text-text-muted"
            >
              {format}
            </span>
          ))}
        </div>

        <p className="text-[11px] leading-5 text-text-muted">
          绿色格式直接送入转写引擎；其余格式会先经 ffmpeg 转成 16kHz 单声道 WAV。
        </p>
      </div>
    </div>
  );
}
