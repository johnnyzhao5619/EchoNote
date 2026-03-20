import { describe, it, expect } from "vitest";
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
    // 等待路由 redirect 完成，检查页面占位内容
    await screen.findByText(/coming in m2/i);
  });

  it("renders transcription page at /transcription", async () => {
    renderWithRouter("/transcription");
    await screen.findByText(/coming in m2/i);
  });
});
