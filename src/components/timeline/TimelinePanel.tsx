import { useEffect } from "react";

import { format } from "date-fns";

import { daysInRange } from "@/lib/timeUtils";
import { eventOccursOnDay } from "@/lib/timelineLayout";
import { useTimelineStore } from "@/store/timeline";

export function TimelinePanel() {
  const {
    events,
    viewMode,
    viewRange,
    fetchRange,
    search,
    setViewMode,
    navigatePrev,
    navigateNext,
    navigateToday,
  } = useTimelineStore();

  useEffect(() => {
    void fetchRange(viewRange.start, viewRange.end);
  }, [fetchRange, viewRange.end, viewRange.start]);

  const days = daysInRange(viewRange.start.getTime(), viewRange.end.getTime());

  return (
    <div className="flex h-full flex-col gap-4 overflow-auto p-4">
      <div className="space-y-2">
        <p className="text-xs uppercase tracking-[0.2em] text-text-muted">Timeline</p>
        <input
          type="search"
          placeholder="Search events"
          onChange={(event) => {
            void search(event.target.value);
          }}
          className="w-full rounded-md border border-border bg-bg-muted px-3 py-2"
        />
      </div>

      <div className="flex flex-wrap gap-2">
        {(["month", "week", "day"] as const).map((mode) => (
          <button
            key={mode}
            type="button"
            onClick={() => {
              void setViewMode(mode);
            }}
            className={`rounded-md border px-3 py-1.5 text-sm capitalize ${
              viewMode === mode ? "bg-bg-hover text-text-primary" : "text-text-muted"
            }`}
          >
            {mode}
          </button>
        ))}
      </div>

      <div className="flex gap-2">
        <button
          type="button"
          onClick={() => {
            void navigatePrev();
          }}
          className="rounded-md border px-3 py-1.5 text-sm"
        >
          Prev
        </button>
        <button
          type="button"
          onClick={() => {
            void navigateToday();
          }}
          className="rounded-md border px-3 py-1.5 text-sm"
        >
          Today
        </button>
        <button
          type="button"
          onClick={() => {
            void navigateNext();
          }}
          className="rounded-md border px-3 py-1.5 text-sm"
        >
          Next
        </button>
      </div>

      <div className="grid grid-cols-7 gap-1" aria-label="Timeline mini calendar">
        {days.map((day) => {
          const hasEvents = events.some((event) => eventOccursOnDay(event, day));

          return (
            <div
              key={day.toISOString()}
              className="rounded-md border border-border bg-bg-panel px-2 py-1 text-center text-xs"
            >
              <div>{format(day, "d")}</div>
              <div className="mt-1 flex justify-center">
                {hasEvents ? <span className="h-1.5 w-1.5 rounded-full bg-blue-500" /> : null}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
