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

describe("Shell", () => {
  it("renders activity bar", async () => {
    renderApp();
    expect(
      await screen.findByRole("navigation", { name: /activity bar/i })
    ).toBeInTheDocument();
  });

  it("renders children in main content area", async () => {
    renderApp("/recording");
    await screen.findByRole("navigation", { name: /activity bar/i });
    expect(screen.getByRole("main")).toBeInTheDocument();
  });

  it("renders status bar", async () => {
    renderApp();
    await screen.findByRole("navigation", { name: /activity bar/i });
    expect(screen.getByRole("contentinfo")).toBeInTheDocument();
  });
});
