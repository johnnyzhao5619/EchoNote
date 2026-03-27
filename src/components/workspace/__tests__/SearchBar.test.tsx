import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen } from "@testing-library/react";

const mockNavigate = vi.fn();

vi.mock("@tanstack/react-router", () => ({
  useNavigate: () => mockNavigate,
}));

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

import { useWorkspaceStore } from "@/store/workspace";
import { SearchBar } from "../SearchBar";

describe("SearchBar", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    Object.values(mockCommands).forEach((fn) => fn.mockReset());
    mockCommands.searchWorkspace.mockResolvedValue({
      status: "ok",
      data: [
        {
          document_id: "doc-1",
          title: "Launch Notes",
          snippet: "<mark>Launch</mark> notes",
          rank: -1,
          folder_id: "folder-1",
          updated_at: 1,
        },
      ],
    });

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

  afterEach(() => {
    vi.useRealTimers();
  });

  it("debounces search and renders highlighted snippets", async () => {
    render(<SearchBar />);

    fireEvent.change(screen.getByPlaceholderText("搜索文档…"), {
      target: { value: "Launch" },
    });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(300);
      await Promise.resolve();
    });

    expect(mockCommands.searchWorkspace).toHaveBeenCalledWith("Launch");
    expect(screen.getByText("Launch Notes")).toBeInTheDocument();
    expect(screen.getByText((_, node) => node?.innerHTML === "<mark>Launch</mark> notes")).toBeInTheDocument();
  });

  it("navigates to the workspace document route when selecting a result", async () => {
    render(<SearchBar />);

    fireEvent.change(screen.getByPlaceholderText("搜索文档…"), {
      target: { value: "Launch" },
    });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(300);
      await Promise.resolve();
    });

    fireEvent.click(screen.getByText("Launch Notes"));

    expect(mockNavigate).toHaveBeenCalledWith({
      to: "/workspace/$folderId/$docId",
      params: { folderId: "folder-1", docId: "doc-1" },
    });
  });
});
