import { beforeEach, describe, expect, it, vi } from "vitest";
import { act } from "@testing-library/react";

const { mockCommands } = vi.hoisted(() => ({
  mockCommands: {
    listFolderTree: vi.fn(),
    listDocumentsInFolder: vi.fn(),
    createFolder: vi.fn(),
    renameFolder: vi.fn(),
    deleteFolder: vi.fn(),
    getDocument: vi.fn(),
    createDocument: vi.fn(),
    updateDocument: vi.fn(),
    deleteDocument: vi.fn(),
    searchWorkspace: vi.fn(),
    importFileToWorkspace: vi.fn(),
    exportDocument: vi.fn(),
  },
}));

vi.mock("@/lib/bindings", () => ({
  commands: mockCommands,
}));

import { useWorkspaceStore } from "../workspace";

describe("useWorkspaceStore", () => {
  beforeEach(() => {
    Object.values(mockCommands).forEach((fn) => fn.mockReset());
    mockCommands.listFolderTree.mockResolvedValue({ status: "ok", data: [] });
    mockCommands.listDocumentsInFolder.mockResolvedValue({ status: "ok", data: [] });
    mockCommands.searchWorkspace.mockResolvedValue({ status: "ok", data: [] });

    useWorkspaceStore.setState({
      folders: [],
      currentFolderId: null,
      documents: [],
      currentDoc: null,
      searchQuery: "",
      searchResults: [],
      isSearching: false,
    });
  });

  it("selectFolder loads folder documents", async () => {
    mockCommands.listDocumentsInFolder.mockResolvedValue({
      status: "ok",
      data: [{ id: "doc-1", title: "Doc", folder_id: "folder-1" }],
    });

    await act(async () => {
      await useWorkspaceStore.getState().selectFolder("folder-1");
    });

    expect(mockCommands.listDocumentsInFolder).toHaveBeenCalledWith("folder-1");
    expect(useWorkspaceStore.getState().currentFolderId).toBe("folder-1");
    expect(useWorkspaceStore.getState().documents).toHaveLength(1);
  });

  it("search stores async search results", async () => {
    mockCommands.searchWorkspace.mockResolvedValue({
      status: "ok",
      data: [{ document_id: "doc-1", title: "Doc", snippet: "<mark>Echo</mark>", rank: -1, folder_id: null, updated_at: 1 }],
    });

    await act(async () => {
      await useWorkspaceStore.getState().search("Echo");
    });

    const state = useWorkspaceStore.getState();
    expect(state.isSearching).toBe(false);
    expect(state.searchResults).toHaveLength(1);
    expect(state.searchResults[0].document_id).toBe("doc-1");
  });

  it("deleteFolder clears current selection when deleting active folder", async () => {
    useWorkspaceStore.setState({ currentFolderId: "folder-1", documents: [{ id: "doc-1" } as any] });
    mockCommands.deleteFolder.mockResolvedValue({ status: "ok", data: null });

    await act(async () => {
      await useWorkspaceStore.getState().deleteFolder("folder-1");
    });

    const state = useWorkspaceStore.getState();
    expect(state.currentFolderId).toBeNull();
    expect(state.documents).toEqual([]);
  });
});
