import { describe, it, expect } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
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

describe("M1 Integration: Shell + Router + Theme", () => {
  it("renders full app shell with all layout regions", async () => {
    renderApp();
    await waitFor(() => {
      expect(screen.getByRole("navigation", { name: /activity bar/i }))
        .toBeInTheDocument();
      expect(screen.getByRole("contentinfo"))
        .toBeInTheDocument(); // StatusBar
      expect(screen.getByRole("main"))
        .toBeInTheDocument();  // 主内容区
    });
  });

  it("default route redirects to /recording and shows placeholder", async () => {
    renderApp("/");
    await screen.findByText(/coming in m2/i);
  });

  it("navigating to /workspace shows workspace placeholder", async () => {
    renderApp("/workspace");
    await screen.findByText(/coming in m4/i);
  });

  it("navigating to /settings shows settings placeholder", async () => {
    renderApp("/settings");
    await screen.findByText(/coming in m5/i);
  });
});
