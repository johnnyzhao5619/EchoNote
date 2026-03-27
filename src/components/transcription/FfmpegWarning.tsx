import { useEffect, useState } from "react";
import { platform } from "@tauri-apps/plugin-os";
import { ExternalLink, TriangleAlert } from "lucide-react";

interface InstallInstruction {
  label: string;
  command: string;
  downloadUrl?: string;
}

function getInstallInstructions(os: string): InstallInstruction[] {
  switch (os) {
    case "macos":
      return [{ label: "Homebrew", command: "brew install ffmpeg" }];
    case "windows":
      return [
        { label: "winget", command: "winget install ffmpeg" },
        {
          label: "手动下载",
          command: "",
          downloadUrl: "https://www.gyan.dev/ffmpeg/builds/",
        },
      ];
    case "linux":
      return [
        { label: "apt (Debian/Ubuntu)", command: "sudo apt install ffmpeg" },
        { label: "dnf (Fedora)", command: "sudo dnf install ffmpeg" },
        { label: "pacman (Arch)", command: "sudo pacman -S ffmpeg" },
      ];
    default:
      return [
        {
          label: "官方文档",
          command: "",
          downloadUrl: "https://ffmpeg.org/download.html",
        },
      ];
  }
}

export function FfmpegWarning() {
  const [os, setOs] = useState("unknown");

  useEffect(() => {
    try {
      setOs(platform());
    } catch {
      setOs("unknown");
    }
  }, []);

  const instructions = getInstallInstructions(os);

  return (
    <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-100">
      <div className="flex items-center gap-2 text-red-50">
        <TriangleAlert className="h-4 w-4" />
        <h3 className="font-medium">需要安装 ffmpeg</h3>
      </div>

      <p className="mt-3 text-xs leading-6 text-red-100/85">
        转写 MP3、MP4、M4A、MOV、MKV、WEBM、OGG 和 FLAC 需要系统安装 ffmpeg。
        WAV 可直接转写。
      </p>

      <div className="mt-3 space-y-2">
        {instructions.map((instruction) => (
          <div
            key={instruction.label}
            className="flex flex-wrap items-center gap-2 text-xs"
          >
            <span className="min-w-32 text-red-100/70">{instruction.label}</span>
            {instruction.command ? (
              <code className="rounded bg-black/20 px-2 py-1 font-mono text-red-50">
                {instruction.command}
              </code>
            ) : null}
            {instruction.downloadUrl ? (
              <a
                href={instruction.downloadUrl}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1 text-red-50 underline decoration-red-200/40 underline-offset-4"
              >
                下载
                <ExternalLink className="h-3 w-3" />
              </a>
            ) : null}
          </div>
        ))}
      </div>

      <p className="mt-3 text-[11px] text-red-100/70">
        安装完成后重启 EchoNote，再重新添加需要转码的文件。
      </p>
    </div>
  );
}
