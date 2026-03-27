import { describe, expect, it } from "vitest";

import {
  eventOccursOnDay,
  getClampedEventBlock,
} from "../timelineLayout";

const day = new Date("2026-03-20T00:00:00");

describe("timelineLayout", () => {
  it("treats overnight events as occurring on both days", () => {
    const event = {
      start_at: new Date("2026-03-19T23:30:00").getTime(),
      end_at: new Date("2026-03-20T01:00:00").getTime(),
    };

    expect(eventOccursOnDay(event, new Date("2026-03-19T00:00:00"))).toBe(true);
    expect(eventOccursOnDay(event, new Date("2026-03-20T00:00:00"))).toBe(true);
  });

  it("enforces a 30px minimum block height", () => {
    const block = getClampedEventBlock(
      new Date("2026-03-20T09:00:00").getTime(),
      new Date("2026-03-20T09:10:00").getTime(),
      day.getTime(),
    );

    expect(block.heightPx).toBe(30);
    expect(block.topPx).toBe(540);
  });
});
