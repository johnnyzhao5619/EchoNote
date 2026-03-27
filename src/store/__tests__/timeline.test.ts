import { act } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { mockCommands } = vi.hoisted(() => ({
  mockCommands: {
    listTimelineEvents: vi.fn(),
    searchTimelineEvents: vi.fn(),
    createTimelineEvent: vi.fn(),
    updateTimelineEvent: vi.fn(),
    deleteTimelineEvent: vi.fn(),
    listRecordings: vi.fn(),
    listAllDocuments: vi.fn(),
  },
}));

vi.mock("@/lib/bindings", () => ({ commands: mockCommands }));

import { useTimelineStore } from "../timeline";

describe("useTimelineStore", () => {
  beforeEach(() => {
    Object.values(mockCommands).forEach((fn) => fn.mockReset());
    useTimelineStore.setState({
      events: [],
      anchorDate: new Date("2026-03-20T00:00:00"),
      viewMode: "month",
      viewRange: {
        start: new Date("2026-03-01T00:00:00"),
        end: new Date("2026-03-31T23:59:59"),
      },
      selectedEventId: null,
      linkableRecordings: [],
      linkableDocuments: [],
      searchQuery: "",
      isLoading: false,
      error: null,
    });
  });

  it("fetchRange hydrates events for the current window", async () => {
    mockCommands.listTimelineEvents.mockResolvedValue({
      status: "ok",
      data: [{
        id: "evt-1",
        title: "Demo",
        start_at: 1000,
        end_at: 2000,
        description: null,
        tags: [],
        recording_id: null,
        document_id: null,
        created_at: 999,
      }],
    });

    await act(async () => {
      await useTimelineStore.getState().fetchRange(new Date(0), new Date(5000));
    });

    expect(mockCommands.listTimelineEvents).toHaveBeenCalledWith(0, 5000);
    expect(useTimelineStore.getState().events).toHaveLength(1);
  });

  it("loadLinkables loads both recordings and documents for the modal", async () => {
    mockCommands.listRecordings.mockResolvedValue({
      status: "ok",
      data: [{ id: "rec-1", title: "Interview" }],
    });
    mockCommands.listAllDocuments.mockResolvedValue({
      status: "ok",
      data: [{ id: "doc-1", title: "Summary" }],
    });

    await act(async () => {
      await useTimelineStore.getState().loadLinkables();
    });

    expect(useTimelineStore.getState().linkableRecordings).toHaveLength(1);
    expect(useTimelineStore.getState().linkableDocuments).toHaveLength(1);
  });
});
