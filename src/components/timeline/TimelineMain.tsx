import { useMemo, useState } from "react";

import { format, isSameDay, isSameMonth } from "date-fns";

import { daysInRange } from "@/lib/timeUtils";
import {
  eventOccursOnDay,
  getClampedEventBlock,
  HOUR_HEIGHT_PX,
} from "@/lib/timelineLayout";
import { useTimelineStore } from "@/store/timeline";

import { EventCard } from "./EventCard";
import { EventModal } from "./EventModal";

type ModalState =
  | { eventId: string }
  | { defaultStartMs: number }
  | null;

const DAY_COLUMN_HEIGHT_PX = HOUR_HEIGHT_PX * 24;

export function TimelineMain() {
  const {
    events,
    viewMode,
    viewRange,
    selectedEventId,
    selectEvent,
  } = useTimelineStore();
  const [modalState, setModalState] = useState<ModalState>(null);

  const days = useMemo(
    () => daysInRange(viewRange.start.getTime(), viewRange.end.getTime()),
    [viewRange.end, viewRange.start],
  );
  const selectedEvent = modalState && "eventId" in modalState
    ? events.find((event) => event.id === modalState.eventId)
    : undefined;

  function openCreateModal(defaultStartMs: number) {
    selectEvent(null);
    setModalState({ defaultStartMs });
  }

  function openEditModal(eventId: string) {
    selectEvent(eventId);
    setModalState({ eventId });
  }

  function renderMonthView() {
    return (
      <div className="grid grid-cols-7 gap-2" role="grid">
        {days.map((day) => {
          const dayEvents = events.filter((event) => eventOccursOnDay(event, day));

          return (
            <div
              key={day.toISOString()}
              role="gridcell"
              aria-label={format(day, "MMMM d, yyyy")}
              onClick={() => openCreateModal(day.getTime())}
              className={`min-h-32 rounded-lg border p-2 ${
                isSameMonth(day, viewRange.start) ? "bg-bg-panel" : "bg-bg-muted/50"
              }`}
            >
              <div className="mb-2 text-sm font-medium">{format(day, "d")}</div>
              <div className="space-y-2">
                {dayEvents.map((event) => (
                  <div
                    key={event.id}
                    onClick={(clickEvent) => {
                      clickEvent.stopPropagation();
                      openEditModal(event.id);
                    }}
                  >
                    <EventCard event={event} compact />
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    );
  }

  function renderTimedView(mode: "week" | "day") {
    const visibleDays = mode === "day"
      ? [viewRange.start]
      : days;

    return (
      <div className={`grid gap-3 ${mode === "day" ? "grid-cols-1" : "grid-cols-7"}`}>
        {visibleDays.map((day) => {
          const dayStartMs = day.getTime();
          const dayEvents = events.filter((event) => eventOccursOnDay(event, day));

          return (
            <div
              key={day.toISOString()}
              className="rounded-lg border bg-bg-panel"
            >
              <button
                type="button"
                onClick={() => openCreateModal(dayStartMs)}
                className="flex w-full items-center justify-between border-b px-3 py-2 text-left"
              >
                <span className="text-sm font-medium">{format(day, "EEE d")}</span>
              </button>
              <div
                className="relative"
                style={{ height: `${DAY_COLUMN_HEIGHT_PX}px` }}
              >
                {dayEvents.map((event) => {
                  const block = getClampedEventBlock(event.start_at, event.end_at, dayStartMs);
                  const testIdPrefix = mode === "week" ? "week-event" : "day-event";

                  return (
                    <div
                      key={`${event.id}-${day.toISOString()}`}
                      data-testid={`${testIdPrefix}-${event.id}`}
                      className="absolute inset-x-2"
                      style={{
                        top: `${block.topPx}px`,
                        height: `${block.heightPx}px`,
                      }}
                      onClick={(clickEvent) => {
                        clickEvent.stopPropagation();
                        openEditModal(event.id);
                      }}
                    >
                      <EventCard event={event} compact={block.heightPx < 56} />
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {viewMode === "month" ? renderMonthView() : null}
      {viewMode === "week" ? renderTimedView("week") : null}
      {viewMode === "day" ? renderTimedView("day") : null}

      {modalState ? (
        <EventModal
          event={selectedEventId ? selectedEvent : undefined}
          defaultStartMs={"defaultStartMs" in modalState ? modalState.defaultStartMs : undefined}
          onClose={() => setModalState(null)}
        />
      ) : null}
    </div>
  );
}
