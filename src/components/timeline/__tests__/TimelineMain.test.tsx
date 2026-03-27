import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

let timelineState: any;

vi.mock("@/store/timeline", () => ({
  useTimelineStore: () => timelineState,
}));

vi.mock("../EventModal", () => ({
  EventModal: ({ defaultStartMs }: { defaultStartMs?: number }) => (
    <div data-testid="timeline-modal">{String(defaultStartMs)}</div>
  ),
}));

import { TimelineMain } from "../TimelineMain";

describe("TimelineMain", () => {
  it("highlights event days in month view and opens create modal on empty cell click", () => {
    timelineState = {
      events: [{
        id: "evt-1",
        title: "Demo",
        start_at: new Date("2026-03-20T09:00:00").getTime(),
        end_at: new Date("2026-03-20T10:00:00").getTime(),
        description: null,
        tags: [],
        recording_id: null,
        document_id: null,
        created_at: 1,
      }],
      viewMode: "month",
      viewRange: {
        start: new Date("2026-03-01T00:00:00"),
        end: new Date("2026-03-31T23:59:59"),
      },
      selectedEventId: null,
      selectEvent: vi.fn(),
    };

    render(<TimelineMain />);
    fireEvent.click(screen.getByRole("gridcell", { name: /March 20, 2026/i }));

    expect(screen.getByTestId("timeline-modal")).toBeInTheDocument();
    expect(screen.getByText("Demo")).toBeInTheDocument();
  });

  it("uses a minimum 30px height in week view", () => {
    timelineState = {
      events: [{
        id: "evt-2",
        title: "Short",
        start_at: new Date("2026-03-20T09:00:00").getTime(),
        end_at: new Date("2026-03-20T09:10:00").getTime(),
        description: null,
        tags: [],
        recording_id: null,
        document_id: null,
        created_at: 1,
      }],
      viewMode: "week",
      viewRange: {
        start: new Date("2026-03-15T00:00:00"),
        end: new Date("2026-03-21T23:59:59"),
      },
      selectedEventId: null,
      selectEvent: vi.fn(),
    };

    render(<TimelineMain />);
    expect(screen.getByTestId("week-event-evt-2")).toHaveStyle({ height: "30px" });
  });
});
