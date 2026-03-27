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

  it("createDocument updates the list and returns the new document id without opening it", async () => {
    const openDocumentSpy = vi.spyOn(useWorkspaceStore.getState(), "openDocument");
    const resultDoc = {
      id: "doc-new",
      title: "New Note",
      folder_id: "folder-1",
      source_type: "note",
      has_transcript: false,
      has_summary: false,
      has_meeting_brief: false,
      recording_id: null,
      created_at: 1,
      updated_at: 1,
    };

    mockCommands.createDocument.mockResolvedValue({
      status: "ok",
      data: resultDoc,
    });

    await act(async () => {
      const createdId = await useWorkspaceStore.getState().createDocument("New Note", "folder-1");
      expect(createdId).toBe("doc-new");
    });

    expect(mockCommands.createDocument).toHaveBeenCalledWith("New Note", "folder-1", "");
    expect(useWorkspaceStore.getState().documents[0]).toMatchObject(resultDoc);
    expect(openDocumentSpy).not.toHaveBeenCalled();
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

  it("search keeps only the latest async result", async () => {
    let resolveFirst: ((value: { status: "ok"; data: Array<{ document_id: string; title: string; snippet: string; rank: number; folder_id: string | null; updated_at: number }> }) => void) | undefined;
    mockCommands.searchWorkspace
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            resolveFirst = resolve;
          }),
      )
      .mockResolvedValueOnce({
        status: "ok",
        data: [
          {
            document_id: "doc-new",
            title: "New",
            snippet: "<mark>new</mark>",
            rank: -1,
            folder_id: "folder-1",
            updated_at: 2,
          },
        ],
      });

    useWorkspaceStore.getState().setSearchQuery("old");
    const firstSearch = useWorkspaceStore.getState().search("old");
    useWorkspaceStore.getState().setSearchQuery("new");
    await useWorkspaceStore.getState().search("new");

    resolveFirst?.({
      status: "ok",
      data: [
        {
          document_id: "doc-old",
          title: "Old",
          snippet: "<mark>old</mark>",
          rank: -2,
          folder_id: "folder-2",
          updated_at: 1,
        },
      ],
    });
    await firstSearch;

    const state = useWorkspaceStore.getState();
    expect(state.searchResults).toHaveLength(1);
    expect(state.searchResults[0].document_id).toBe("doc-new");
    expect(state.isSearching).toBe(false);
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
