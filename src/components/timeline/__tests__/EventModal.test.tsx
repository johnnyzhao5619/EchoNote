import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const createEvent = vi.fn();
const updateEvent = vi.fn();
const deleteEvent = vi.fn();
const loadLinkables = vi.fn();

vi.mock("@/store/timeline", () => ({
  useTimelineStore: () => ({
    createEvent,
    updateEvent,
    deleteEvent,
    loadLinkables,
    linkableRecordings: [{ id: "rec-1", title: "Interview" }],
    linkableDocuments: [{ id: "doc-1", title: "Summary", folder_id: null }],
  }),
}));

import { EventModal } from "../EventModal";

describe("EventModal", () => {
  it("creates an event with tag chips and selected links", async () => {
    render(
      <EventModal
        defaultStartMs={new Date("2026-03-20T09:00:00").getTime()}
        onClose={() => {}}
      />,
    );

    fireEvent.change(screen.getByLabelText(/Title/i), {
      target: { value: "Planning" },
    });
    fireEvent.change(screen.getByPlaceholderText(/Add tag/i), {
      target: { value: "work" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Add tag/i }));
    fireEvent.change(screen.getByLabelText(/Recording/i), {
      target: { value: "rec-1" },
    });
    fireEvent.change(screen.getByLabelText(/Document/i), {
      target: { value: "doc-1" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Create/i }));

    await waitFor(() => expect(createEvent).toHaveBeenCalled());
    expect(loadLinkables).toHaveBeenCalled();
    expect(screen.getByText("work")).toBeInTheDocument();
    expect(createEvent).toHaveBeenCalledWith(
      expect.objectContaining({
        title: "Planning",
        recording_id: "rec-1",
        document_id: "doc-1",
      }),
    );
  });
});
