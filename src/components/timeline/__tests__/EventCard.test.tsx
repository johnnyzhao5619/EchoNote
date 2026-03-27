import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { EventCard } from "../EventCard";

const event = {
  id: "evt-1",
  title: "Design Review",
  start_at: new Date("2026-03-20T09:00:00").getTime(),
  end_at: new Date("2026-03-20T10:30:00").getTime(),
  description: "Review timeline UI",
  tags: ["design", "review"],
  recording_id: "rec-1",
  document_id: "doc-1",
  created_at: 1,
};

describe("EventCard", () => {
  it("renders title, time range, tags, and link indicators", () => {
    render(<EventCard event={event} />);

    expect(screen.getByText("Design Review")).toBeInTheDocument();
    expect(screen.getByText(/09:00/)).toBeInTheDocument();
    expect(screen.getByText("design")).toBeInTheDocument();
    expect(screen.getByLabelText("Linked recording")).toBeInTheDocument();
    expect(screen.getByLabelText("Linked document")).toBeInTheDocument();
  });

  it("invokes onClick and hides metadata in compact mode", () => {
    const onClick = vi.fn();

    render(<EventCard event={event} compact onClick={onClick} />);
    fireEvent.click(screen.getByRole("button", { name: /Design Review/i }));

    expect(onClick).toHaveBeenCalledWith(event);
    expect(screen.queryByText("design")).not.toBeInTheDocument();
  });
});
