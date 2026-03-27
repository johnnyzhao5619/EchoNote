import {
  addDays,
  addMonths,
  addWeeks,
  eachDayOfInterval,
  endOfDay,
  endOfMonth,
  endOfWeek,
  format,
  startOfDay,
  startOfMonth,
  startOfWeek,
} from "date-fns";

export type TimelineViewMode = "month" | "week" | "day";

export function datetimeLocalToMs(value: string): number {
  return new Date(value).getTime();
}

export function msToDatetimeLocal(ms: number): string {
  const date = new Date(ms);
  const offsetMs = date.getTimezoneOffset() * 60 * 1000;
  return new Date(date.getTime() - offsetMs).toISOString().slice(0, 16);
}

export function monthBounds(date: Date) {
  return { start: startOfMonth(date).getTime(), end: endOfMonth(date).getTime() };
}

export function weekBounds(date: Date) {
  return {
    start: startOfWeek(date, { weekStartsOn: 0 }).getTime(),
    end: endOfWeek(date, { weekStartsOn: 0 }).getTime(),
  };
}

export function dayBounds(date: Date) {
  return { start: startOfDay(date).getTime(), end: endOfDay(date).getTime() };
}

export function daysInRange(startMs: number, endMs: number) {
  return eachDayOfInterval({ start: new Date(startMs), end: new Date(endMs) });
}

export function formatEventTime(ms: number) {
  return format(new Date(ms), "HH:mm");
}

export function formatEventDate(ms: number) {
  return format(new Date(ms), "MMM d");
}

export function rangeForView(anchor: Date, viewMode: TimelineViewMode) {
  if (viewMode === "month") {
    return monthBounds(anchor);
  }
  if (viewMode === "week") {
    return weekBounds(anchor);
  }
  return dayBounds(anchor);
}

export function shiftAnchor(anchor: Date, viewMode: TimelineViewMode, amount: number) {
  if (viewMode === "month") {
    return addMonths(anchor, amount);
  }
  if (viewMode === "week") {
    return addWeeks(anchor, amount);
  }
  return addDays(anchor, amount);
}
