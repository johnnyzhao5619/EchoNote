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
    getDocument: vi.fn().mockResolvedValue({
      status: "ok",
      data: {
        id: "doc-1",
        title: "Launch Notes",
        folder_id: "folder-1",
        source_type: "note",
        recording_id: null,
        created_at: 1,
        updated_at: 2,
        assets: [
          {
            id: "asset-1",
            role: "transcript",
            language: "zh-CN",
            content: "document body",
            updated_at: 2,
          },
        ],
      },
    }),
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

  it("renders folder-scoped workspace route at /workspace/$folderId", async () => {
    renderApp("/workspace/folder-1");

    expect(await screen.findByRole("button", { name: /新建文档/i })).toBeInTheDocument();
  });

  it("renders document route at /workspace/$folderId/$docId", async () => {
    renderApp("/workspace/folder-1/doc-1");

    expect(await screen.findByRole("textbox", { name: /标题/i })).toHaveValue("Launch Notes");
    expect(screen.getByRole("button", { name: /编辑正文/i })).toBeInTheDocument();
    expect(screen.queryByRole("tab")).not.toBeInTheDocument();
  });
});
