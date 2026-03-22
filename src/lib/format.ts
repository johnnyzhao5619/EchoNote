// src/lib/format.ts
// Shared formatting utilities for time and date display.

export function formatDuration(ms: number): string {
  const totalSec = Math.floor(ms / 1000);
  const m = Math.floor(totalSec / 60);
  const s = totalSec % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

export function formatDate(ts: number): string {
  return new Date(ts).toLocaleString();
}
