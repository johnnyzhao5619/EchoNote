import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import {
  RouterProvider,
  createMemoryHistory,
  createRouter,
} from "@tanstack/react-router";

import { routeTree } from "@/routeTree.gen";

vi.mock("@/lib/bindings", () => ({
  commands: {
    listFolderTree: vi.fn().mockResolvedValue({ status: "ok", data: [] }),
    listDocumentsInFolder: vi.fn().mockResolvedValue({ status: "ok", data: [] }),
    createFolder: vi.fn(),
    renameFolder: vi.fn(),
    deleteFolder: vi.fn(),
    getDocument: vi.fn(),
    createDocument: vi.fn(),
    updateDocument: vi.fn(),
    deleteDocument: vi.fn(),
    searchWorkspace: vi.fn().mockResolvedValue({ status: "ok", data: [] }),
    importFileToWorkspace: vi.fn(),
    exportDocument: vi.fn(),
  },
}));

function renderApp(initialPath = "/workspace") {
  const history = createMemoryHistory({ initialEntries: [initialPath] });
  const router = createRouter({ routeTree, history });
  return render(<RouterProvider router={router} />);
}

describe("workspace routing", () => {
  it("mounts the new workspace panel on /workspace", async () => {
    renderApp("/workspace");

    expect(await screen.findByRole("button", { name: /新建文件夹/i })).toBeInTheDocument();
  });
});
