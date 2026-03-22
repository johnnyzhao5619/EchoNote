// src/components/workspace/SubtitleEditor.tsx
// Full-page subtitle editor: segment table with inline editing,
// playback sync, language selector, and SRT/VTT/LRC export.

import { useState, useEffect, useRef, useCallback } from "react";
import { commands } from "@/lib/bindings";
import type { SegmentRow, SubtitleLanguage, SubtitleFormat } from "@/lib/bindings";
import { Play, Pause, Download, ChevronDown } from "lucide-react";
import { formatDuration } from "@/lib/format";

// ── Props ─────────────────────────────────────────────────────────────────────

interface SubtitleEditorProps {
  recordingId: string;
  filePath: string;      // WAV absolute path
  durationMs: number;
}

// ── Time helpers ──────────────────────────────────────────────────────────────

function formatTime(ms: number): string {
  const total = ms / 1000;
  const m = Math.floor(total / 60);
  const s = (total % 60).toFixed(2).padStart(5, "0");
  return `${m}:${s}`;
}

function parseTime(s: string): number {
  const [mStr, rest] = s.split(":");
  return (parseInt(mStr ?? "0", 10) * 60 + parseFloat(rest ?? "0")) * 1000;
}

// ── Translation language options ──────────────────────────────────────────────

const TRANSLATION_LANGUAGES = [
  { value: "en", label: "英文" },
  { value: "ja", label: "日文" },
  { value: "ko", label: "韩文" },
  { value: "fr", label: "法文" },
  { value: "de", label: "德文" },
  { value: "es", label: "西班牙文" },
  { value: "ru", label: "俄文" },
] as const;

// ── SubtitleEditor ────────────────────────────────────────────────────────────

export function SubtitleEditor({
  recordingId,
  filePath,
  durationMs,
}: SubtitleEditorProps) {
  const audioRef = useRef<HTMLAudioElement>(null);
  const [src, setSrc] = useState<string | null>(null);
  const [playing, setPlaying] = useState(false);
  const [currentMs, setCurrentMs] = useState(0);

  const [segments, setSegments] = useState<SegmentRow[]>([]);
  const [language, setLanguage] = useState<string | null>(null); // null = original only
  const [currentSegmentId, setCurrentSegmentId] = useState<number | null>(null);
  const [showTranslMenu, setShowTranslMenu] = useState(false);

  const rowRefs = useRef<Map<number, HTMLTableRowElement>>(new Map());

  // Resolve asset URL
  useEffect(() => {
    import("@tauri-apps/api/core").then(({ convertFileSrc }) => {
      setSrc(convertFileSrc(filePath));
    });
  }, [filePath]);

  // Load segments
  const loadSegments = useCallback(() => {
    commands
      .getSegmentsWithTranslations(recordingId, language)
      .then((r) => {
        if (r.status === "ok") setSegments(r.data);
      });
  }, [recordingId, language]);

  useEffect(() => {
    loadSegments();
  }, [loadSegments]);

  // Playback time update → highlight current segment
  const handleTimeUpdate = useCallback(() => {
    const ms = (audioRef.current?.currentTime ?? 0) * 1000;
    setCurrentMs(ms);
    const active = segments.find((s) => s.start_ms <= ms && ms <= s.end_ms);
    const newId = active?.id ?? null;
    setCurrentSegmentId((prev) => {
      if (prev !== newId && newId !== null) {
        rowRefs.current.get(newId)?.scrollIntoView({ block: "nearest" });
      }
      return newId;
    });
  }, [segments]);

  // Seek audio to segment start
  const seekTo = (seg: SegmentRow) => {
    if (!audioRef.current) return;
    audioRef.current.currentTime = seg.start_ms / 1000;
    audioRef.current.play().then(() => setPlaying(true)).catch(() => {});
  };

  // Toggle play/pause
  const togglePlay = () => {
    const el = audioRef.current;
    if (!el) return;
    if (el.paused) {
      el.play().then(() => setPlaying(true)).catch(() => {});
    } else {
      el.pause();
      setPlaying(false);
    }
  };

  // Seek via progress bar click
  const handleBarClick = (e: React.MouseEvent<HTMLDivElement>) => {
    const el = audioRef.current;
    if (!el || !durationMs) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const pct = (e.clientX - rect.left) / rect.width;
    el.currentTime = (pct * durationMs) / 1000;
  };

  // Inline timing edit
  const handleTimingBlur = async (
    seg: SegmentRow,
    field: "start_ms" | "end_ms",
    raw: string
  ) => {
    const ms = parseTime(raw);
    const newStart = field === "start_ms" ? ms : seg.start_ms;
    const newEnd = field === "end_ms" ? ms : seg.end_ms;
    if (newStart >= newEnd) return; // silently ignore invalid
    const result = await commands.updateSegmentTiming(seg.id, newStart, newEnd);
    if (result.status === "ok") loadSegments();
  };

  // Inline text / translation edit
  const handleTextBlur = async (
    seg: SegmentRow,
    field: "text" | "translated_text",
    value: string
  ) => {
    if (field === "text") {
      // Transcript text editing is not persisted to DB in this version
      // (transcript segments are write-once from Whisper).
      return;
    }
    if (!language) return;
    const result = await commands.updateSegmentTranslation(seg.id, language, value);
    if (result.status === "ok") loadSegments();
  };

  // Export
  const handleExport = async (fmt: "srt" | "vtt" | "lrc") => {
    const lang: SubtitleLanguage = language
      ? { type: "translation", data: language }
      : { type: "original" };
    const result = await commands.exportSubtitle(recordingId, fmt as SubtitleFormat, lang);
    if (result.status === "ok") {
      alert(`字幕已导出至：\n${result.data}`);
    } else {
      alert(`导出失败`);
    }
  };

  const translLangLabel =
    TRANSLATION_LANGUAGES.find((l) => l.value === language)?.label ?? null;

  const pct = durationMs > 0 ? (currentMs / durationMs) * 100 : 0;

  return (
    <div className="flex flex-col h-full">
      {/* Hidden audio element */}
      {src && (
        <audio
          ref={audioRef}
          src={src}
          onTimeUpdate={handleTimeUpdate}
          onEnded={() => setPlaying(false)}
          onPause={() => setPlaying(false)}
          onPlay={() => setPlaying(true)}
        />
      )}

      {/* ── Playback bar ─────────────────────────────────────────── */}
      <div className="shrink-0 px-4 py-2 border-b border-border-default flex items-center gap-3">
        <button
          onClick={togglePlay}
          className="shrink-0 w-7 h-7 flex items-center justify-center rounded-full bg-accent-primary text-white hover:opacity-90 transition-opacity"
        >
          {playing ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5 ml-0.5" />}
        </button>

        <span className="text-xs text-text-muted w-10 shrink-0 tabular-nums">
          {formatDuration(currentMs)}
        </span>

        <div
          className="flex-1 h-1.5 bg-bg-tertiary rounded-full cursor-pointer relative"
          onClick={handleBarClick}
        >
          <div
            className="absolute inset-y-0 left-0 bg-accent-primary rounded-full"
            style={{ width: `${pct}%` }}
          />
        </div>

        <span className="text-xs text-text-muted w-10 shrink-0 tabular-nums text-right">
          {formatDuration(durationMs)}
        </span>
      </div>

      {/* ── Toolbar ──────────────────────────────────────────────── */}
      <div className="shrink-0 px-4 py-2 border-b border-border-default flex items-center gap-2 flex-wrap">
        {/* Show translation column selector */}
        <div className="relative">
          <button
            onClick={() => setShowTranslMenu((v) => !v)}
            className="flex items-center gap-1 px-2 py-1 rounded border border-border-default text-xs text-text-secondary hover:bg-bg-tertiary transition-colors"
          >
            翻译列：{translLangLabel ?? "无"}
            <ChevronDown className="w-3 h-3" />
          </button>
          {showTranslMenu && (
            <div className="absolute left-0 top-full mt-1 z-10 min-w-[110px] rounded-md border border-border-default bg-bg-primary shadow-lg py-1">
              <button
                onClick={() => { setLanguage(null); setShowTranslMenu(false); }}
                className={[
                  "w-full text-left px-3 py-1.5 text-xs hover:bg-bg-tertiary transition-colors",
                  language === null ? "text-accent-primary font-medium" : "text-text-primary",
                ].join(" ")}
              >
                无（仅原文）
              </button>
              {TRANSLATION_LANGUAGES.map((lang) => (
                <button
                  key={lang.value}
                  onClick={() => { setLanguage(lang.value); setShowTranslMenu(false); }}
                  className={[
                    "w-full text-left px-3 py-1.5 text-xs hover:bg-bg-tertiary transition-colors",
                    language === lang.value ? "text-accent-primary font-medium" : "text-text-primary",
                  ].join(" ")}
                >
                  {lang.label}
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="flex-1" />

        {/* Export buttons */}
        {(["srt", "vtt", "lrc"] as const).map((fmt) => (
          <button
            key={fmt}
            onClick={() => handleExport(fmt)}
            className="flex items-center gap-1 px-2 py-1 rounded border border-border-default text-xs text-text-secondary hover:bg-bg-tertiary transition-colors uppercase"
            title={`导出 ${fmt.toUpperCase()}`}
          >
            <Download className="w-3 h-3" />
            {fmt.toUpperCase()}
          </button>
        ))}
      </div>

      {/* ── Segment table ────────────────────────────────────────── */}
      <div className="flex-1 overflow-auto">
        <table className="w-full text-xs border-collapse">
          <thead className="sticky top-0 bg-bg-secondary z-10">
            <tr>
              <th className="text-left px-2 py-1.5 font-medium text-text-muted border-b border-border-default w-8">#</th>
              <th className="text-left px-2 py-1.5 font-medium text-text-muted border-b border-border-default w-20">开始</th>
              <th className="text-left px-2 py-1.5 font-medium text-text-muted border-b border-border-default w-20">结束</th>
              <th className="text-left px-2 py-1.5 font-medium text-text-muted border-b border-border-default">原文</th>
              {language && (
                <th className="text-left px-2 py-1.5 font-medium text-text-muted border-b border-border-default">
                  {translLangLabel}译文
                </th>
              )}
            </tr>
          </thead>
          <tbody>
            {segments.length === 0 && (
              <tr>
                <td colSpan={language ? 5 : 4} className="px-2 py-6 text-center text-text-muted">
                  暂无段落
                </td>
              </tr>
            )}
            {segments.map((seg, idx) => {
              const isActive = seg.id === currentSegmentId;
              return (
                <tr
                  key={seg.id}
                  ref={(el) => {
                    if (el) rowRefs.current.set(seg.id, el);
                    else rowRefs.current.delete(seg.id);
                  }}
                  className={[
                    "border-b border-border-default/50 transition-colors",
                    isActive ? "bg-accent-primary/10" : "hover:bg-bg-secondary",
                  ].join(" ")}
                >
                  {/* Row number / seek */}
                  <td
                    className="px-2 py-1 text-text-muted cursor-pointer select-none"
                    onClick={() => seekTo(seg)}
                    title="跳转到此段"
                  >
                    {isActive ? "▶" : idx + 1}
                  </td>

                  {/* Start time */}
                  <td className="px-1 py-1">
                    <EditableTime
                      value={seg.start_ms}
                      onBlur={(v) => handleTimingBlur(seg, "start_ms", v)}
                    />
                  </td>

                  {/* End time */}
                  <td className="px-1 py-1">
                    <EditableTime
                      value={seg.end_ms}
                      onBlur={(v) => handleTimingBlur(seg, "end_ms", v)}
                    />
                  </td>

                  {/* Original text (read-only display) */}
                  <td className="px-2 py-1 text-text-primary">
                    {seg.text}
                  </td>

                  {/* Translation (editable) */}
                  {language && (
                    <td className="px-1 py-1">
                      <EditableText
                        value={seg.translated_text ?? ""}
                        placeholder="添加译文…"
                        onBlur={(v) => handleTextBlur(seg, "translated_text", v)}
                      />
                    </td>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── EditableTime ──────────────────────────────────────────────────────────────

function EditableTime({
  value,
  onBlur,
}: {
  value: number;
  onBlur: (raw: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [raw, setRaw] = useState(formatTime(value));

  useEffect(() => {
    if (!editing) setRaw(formatTime(value));
  }, [value, editing]);

  if (!editing) {
    return (
      <span
        className="block px-1 py-0.5 rounded cursor-pointer hover:bg-bg-tertiary text-text-secondary font-mono tabular-nums"
        onClick={() => setEditing(true)}
      >
        {raw}
      </span>
    );
  }

  return (
    <input
      autoFocus
      value={raw}
      onChange={(e) => setRaw(e.target.value)}
      onBlur={() => { setEditing(false); onBlur(raw); }}
      onKeyDown={(e) => {
        if (e.key === "Enter") { setEditing(false); onBlur(raw); }
        if (e.key === "Escape") { setEditing(false); setRaw(formatTime(value)); }
      }}
      className="w-full px-1 py-0.5 bg-bg-secondary border border-accent-primary rounded text-xs font-mono focus:outline-none"
    />
  );
}

// ── EditableText ──────────────────────────────────────────────────────────────

function EditableText({
  value,
  placeholder,
  onBlur,
}: {
  value: string;
  placeholder?: string;
  onBlur: (v: string) => void;
}) {
  const [val, setVal] = useState(value);

  useEffect(() => { setVal(value); }, [value]);

  return (
    <input
      value={val}
      onChange={(e) => setVal(e.target.value)}
      onBlur={() => onBlur(val)}
      placeholder={placeholder}
      className="w-full px-1 py-0.5 bg-transparent border-b border-transparent hover:border-border-default focus:border-accent-primary text-text-primary focus:outline-none text-xs"
    />
  );
}
