import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import {
  createMemoryHistory,
  createRouter,
  RouterProvider,
} from "@tanstack/react-router";
import { routeTree } from "../../../routeTree.gen";

function renderApp(initialPath = "/recording") {
  const history = createMemoryHistory({ initialEntries: [initialPath] });
  const router = createRouter({ routeTree, history });
  return render(<RouterProvider router={router} />);
}

describe("ActivityBar", () => {
  it("renders all 5 navigation links", async () => {
    renderApp();
    // 等待路由渲染完成
    await screen.findByRole("navigation", { name: /activity bar/i });
    expect(screen.getByRole("link", { name: /recording/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /transcription/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /workspace/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /timeline/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /settings/i })).toBeInTheDocument();
  });
});
