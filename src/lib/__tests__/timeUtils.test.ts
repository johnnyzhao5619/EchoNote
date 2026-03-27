import { describe, expect, it } from "vitest";

import {
  datetimeLocalToMs,
  msToDatetimeLocal,
  monthBounds,
  weekBounds,
  dayBounds,
} from "../timeUtils";

describe("timeUtils", () => {
  const FIXED_MS = Date.UTC(2026, 2, 20, 14, 30, 0);

  it("round-trips datetime-local strings through local time", () => {
    const localValue = msToDatetimeLocal(FIXED_MS);
    expect(localValue).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/);
    expect(Math.abs(datetimeLocalToMs(localValue) - FIXED_MS)).toBeLessThan(60_000);
  });

  it("returns inclusive month/week/day bounds", () => {
    const ref = new Date("2026-03-20T14:30:00Z");
    const month = monthBounds(ref);
    const week = weekBounds(ref);
    const day = dayBounds(ref);

    expect(month.start).toBeLessThanOrEqual(ref.getTime());
    expect(month.end).toBeGreaterThanOrEqual(ref.getTime());
    expect(week.start).toBeLessThanOrEqual(ref.getTime());
    expect(week.end).toBeGreaterThanOrEqual(ref.getTime());
    expect(day.end - day.start).toBe(86_399_999);
  });
});
