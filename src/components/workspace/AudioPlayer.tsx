// src/components/workspace/AudioPlayer.tsx
// Audio playback for a recording WAV file using Tauri's asset protocol.

import { useEffect, useState, useRef } from "react";
import { Play, Pause, Volume2 } from "lucide-react";
import { formatDuration } from "@/lib/format";

interface AudioPlayerProps {
  filePath: string;
  durationMs: number;
}

// Reuse formatDuration from shared format.ts (ms → "m:ss")
// For currentTime (in seconds), multiply by 1000.
const formatSec = (sec: number) => formatDuration(Math.round(sec) * 1000);

export function AudioPlayer({ filePath, durationMs }: AudioPlayerProps) {
  const [src, setSrc] = useState<string | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [error, setError] = useState(false);
  const audioRef = useRef<HTMLAudioElement>(null);

  useEffect(() => {
    // convertFileSrc converts absolute file path to asset:// URL
    import("@tauri-apps/api/core")
      .then(({ convertFileSrc }) => {
        setSrc(convertFileSrc(filePath));
      })
      .catch(() => setError(true));
  }, [filePath]);

  const totalSec = durationMs / 1000;

  const togglePlay = () => {
    const audio = audioRef.current;
    if (!audio) return;
    if (isPlaying) {
      audio.pause();
    } else {
      audio.play().catch(() => setError(true));
    }
  };

  const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
    const audio = audioRef.current;
    if (!audio) return;
    const t = Number(e.target.value);
    audio.currentTime = t;
    setCurrentTime(t);
  };

  if (error) {
    return (
      <div className="flex items-center gap-2 text-xs text-text-muted px-1">
        <Volume2 className="w-3.5 h-3.5 shrink-0" />
        <span className="truncate">音频文件：{filePath}</span>
      </div>
    );
  }

  if (!src) return null;

  return (
    <div className="flex items-center gap-3 px-1">
      {/* Hidden native audio element for logic */}
      <audio
        ref={audioRef}
        src={src}
        onPlay={() => setIsPlaying(true)}
        onPause={() => setIsPlaying(false)}
        onEnded={() => setIsPlaying(false)}
        onTimeUpdate={() =>
          setCurrentTime(audioRef.current?.currentTime ?? 0)
        }
        onError={() => setError(true)}
        preload="metadata"
      />

      {/* Custom controls */}
      <button
        onClick={togglePlay}
        className="shrink-0 w-7 h-7 rounded-full flex items-center justify-center bg-accent-primary text-white hover:opacity-90 transition-opacity"
        aria-label={isPlaying ? "暂停" : "播放"}
      >
        {isPlaying ? (
          <Pause className="w-3.5 h-3.5 fill-current" />
        ) : (
          <Play className="w-3.5 h-3.5 fill-current ml-0.5" />
        )}
      </button>

      <span className="shrink-0 text-xs text-text-muted w-10 text-right tabular-nums">
        {formatSec(currentTime)}
      </span>

      <input
        type="range"
        min={0}
        max={totalSec || 1}
        step={0.1}
        value={currentTime}
        onChange={handleSeek}
        className="flex-1 h-1 accent-[var(--color-accent-primary)] cursor-pointer"
      />

      <span className="shrink-0 text-xs text-text-muted w-10 tabular-nums">
        {formatSec(totalSec)}
      </span>
    </div>
  );
}
