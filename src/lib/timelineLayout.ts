import { endOfDay, startOfDay } from "date-fns";

const HOUR_HEIGHT_PX = 60;
const MIN_EVENT_HEIGHT_PX = 30;

export function eventOccursOnDay(
  event: { start_at: number; end_at: number },
  day: Date,
): boolean {
  const dayStart = startOfDay(day).getTime();
  const dayEnd = endOfDay(day).getTime();
  return event.end_at >= dayStart && event.start_at <= dayEnd;
}

export function getClampedEventBlock(startAt: number, endAt: number, dayStartMs: number) {
  const dayEndMs = endOfDay(new Date(dayStartMs)).getTime();
  const clampedStart = Math.max(startAt, dayStartMs);
  const clampedEnd = Math.min(endAt, dayEndMs);
  const topPx = ((clampedStart - dayStartMs) / 3_600_000) * HOUR_HEIGHT_PX;
  const heightPx = Math.max(
    ((clampedEnd - clampedStart) / 3_600_000) * HOUR_HEIGHT_PX,
    MIN_EVENT_HEIGHT_PX,
  );

  return { topPx, heightPx };
}

export { HOUR_HEIGHT_PX, MIN_EVENT_HEIGHT_PX };
