import { describe, it } from "vitest";
import { render, screen } from "@testing-library/react";
import {
  createMemoryHistory,
  createRouter,
  RouterProvider,
} from "@tanstack/react-router";
import { routeTree } from "../../routeTree.gen";

function renderWithRouter(initialPath: string) {
  const memoryHistory = createMemoryHistory({ initialEntries: [initialPath] });
  const testRouter = createRouter({ routeTree, history: memoryHistory });
  return render(<RouterProvider router={testRouter} />);
}

describe("routing", () => {
  it("redirects / to /recording", async () => {
    renderWithRouter("/");
    await screen.findByRole("heading", { name: /input/i });
  });

  it("renders transcription page at /transcription", async () => {
    renderWithRouter("/transcription");
    await screen.findByText(/coming in m2/i);
  });
});
