import { render, screen } from "@testing-library/react";
import { createMemoryHistory, createRouter, RouterProvider } from "@tanstack/react-router";
import { describe, it, vi } from "vitest";

import { routeTree } from "../../routeTree.gen";

vi.mock("@/lib/bindings", () => ({
  commands: {
    listTimelineEvents: vi.fn().mockResolvedValue({ status: "ok", data: [] }),
    searchTimelineEvents: vi.fn().mockResolvedValue({ status: "ok", data: [] }),
    createTimelineEvent: vi.fn(),
    updateTimelineEvent: vi.fn(),
    deleteTimelineEvent: vi.fn(),
    listRecordings: vi.fn().mockResolvedValue({ status: "ok", data: [] }),
    listAllDocuments: vi.fn().mockResolvedValue({ status: "ok", data: [] }),
  },
}));

describe("timeline routing", () => {
  it("renders timeline panel in SecondPanel and timeline main in content area", async () => {
    const history = createMemoryHistory({ initialEntries: ["/timeline"] });
    const router = createRouter({ routeTree, history });
    render(<RouterProvider router={router} />);

    await screen.findByPlaceholderText(/Search events/i);
    await screen.findByRole("grid");
  });
});
