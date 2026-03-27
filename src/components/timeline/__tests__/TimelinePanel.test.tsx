import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const storeState = {
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
  viewMode: "month" as const,
  viewRange: {
    start: new Date("2026-03-01T00:00:00"),
    end: new Date("2026-03-31T23:59:59"),
  },
  fetchRange: vi.fn(),
  search: vi.fn(),
  setViewMode: vi.fn(),
  navigatePrev: vi.fn(),
  navigateNext: vi.fn(),
  navigateToday: vi.fn(),
};

vi.mock("@/store/timeline", () => ({
  useTimelineStore: () => storeState,
}));

import { TimelinePanel } from "../TimelinePanel";

describe("TimelinePanel", () => {
  it("renders view mode controls and forwards search input", () => {
    render(<TimelinePanel />);
    fireEvent.change(screen.getByPlaceholderText(/Search events/i), { target: { value: "Demo" } });
    expect(storeState.search).toHaveBeenCalledWith("Demo");
    expect(screen.getByRole("button", { name: /month/i })).toBeInTheDocument();
  });
});
