import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

const mockNavigate = vi.fn();

vi.mock("@tanstack/react-router", () => ({
  useNavigate: () => mockNavigate,
}));

let workspaceState: {
  folders: Array<{
    id: string;
    name: string;
    parent_id: string | null;
    folder_kind: string;
    is_system: boolean;
    document_count: number;
    children: any[];
  }>;
  currentFolderId: string | null;
  searchQuery: string;
  searchResults: any[];
  isSearching: boolean;
  loadFolderTree: ReturnType<typeof vi.fn>;
  selectFolder: ReturnType<typeof vi.fn>;
  createFolder: ReturnType<typeof vi.fn>;
  renameFolder: ReturnType<typeof vi.fn>;
  deleteFolder: ReturnType<typeof vi.fn>;
  setSearchQuery: ReturnType<typeof vi.fn>;
  search: ReturnType<typeof vi.fn>;
  clearSearch: ReturnType<typeof vi.fn>;
  openDocument: ReturnType<typeof vi.fn>;
};

vi.mock("@/store/workspace", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/store/workspace")>();
  return {
    ...actual,
    useWorkspaceStore: () => workspaceState,
  };
});

import {
  getFolderAncestorIds,
  getRootFolderIds,
} from "@/lib/workspace-tree";
import { WorkspacePanel } from "../WorkspacePanel";

function createWorkspaceState(currentFolderId: string | null = null) {
  const loadFolderTree = vi.fn();
  const selectFolder = vi.fn();
  const createFolder = vi.fn();
  const renameFolder = vi.fn();
  const deleteFolder = vi.fn();
  const setSearchQuery = vi.fn();
  const search = vi.fn();
  const clearSearch = vi.fn();
  const openDocument = vi.fn();

  return {
    folders: [
      {
        id: "folder-root",
        name: "Workspace",
        parent_id: null,
        folder_kind: "workspace",
        is_system: false,
        document_count: 3,
        children: [
          {
            id: "folder-child",
            name: "Project A",
            parent_id: "folder-root",
            folder_kind: "workspace",
            is_system: false,
            document_count: 1,
            children: [
              {
                id: "folder-grandchild",
                name: "Research",
                parent_id: "folder-child",
                folder_kind: "workspace",
                is_system: false,
                document_count: 0,
                children: [],
              },
            ],
          },
        ],
      },
    ],
    currentFolderId,
    searchQuery: "",
    searchResults: [],
    isSearching: false,
    loadFolderTree,
    selectFolder,
    createFolder,
    renameFolder,
    deleteFolder,
    setSearchQuery,
    search,
    clearSearch,
    openDocument,
  };
}

describe("WorkspacePanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    workspaceState = createWorkspaceState();
  });

  it("renders folder tree and create action", async () => {
    render(<WorkspacePanel />);

    expect(await screen.findByRole("button", { name: "Workspace" })).toBeInTheDocument();
    expect(screen.queryByRole("tree")).not.toBeInTheDocument();
    expect(screen.queryByRole("treeitem")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /新建文件夹/i })).toBeInTheDocument();
  });

  it("navigates to folder route when selecting a folder", async () => {
    render(<WorkspacePanel />);

    fireEvent.click(await screen.findByRole("button", { name: "Project A" }));

    expect(mockNavigate).toHaveBeenCalledWith({
      to: "/workspace/$folderId",
      params: { folderId: "folder-child" },
    });
  });

  it("keeps expansion and selection as separate actions without tree widget roles", async () => {
    render(<WorkspacePanel />);

    const rootToggle = await screen.findByRole("button", { name: "折叠 Workspace" });
    expect(rootToggle).toHaveAttribute("aria-expanded", "true");

    fireEvent.click(screen.getByRole("button", { name: /展开 Project A/i }));
    expect(mockNavigate).not.toHaveBeenCalled();

    const grandchildSelect = await screen.findByRole("button", { name: "Research" });
    expect(grandchildSelect).not.toHaveAttribute("aria-current");

    fireEvent.click(screen.getByRole("button", { name: "Project A" }));
    expect(mockNavigate).toHaveBeenCalledWith({
      to: "/workspace/$folderId",
      params: { folderId: "folder-child" },
    });

    expect(screen.getByRole("button", { name: "折叠 Project A" })).toHaveAttribute(
      "aria-expanded",
      "true",
    );
  });

  it("keeps manual collapse collapsed after route auto-expands the ancestor chain", async () => {
    workspaceState.currentFolderId = "folder-grandchild";

    render(<WorkspacePanel />);

    expect(await screen.findByRole("button", { name: "Research" })).toHaveAttribute(
      "aria-current",
      "page",
    );

    fireEvent.click(screen.getByRole("button", { name: /折叠 Project A/i }));

    expect(await screen.findByRole("button", { name: /展开 Project A/i })).toHaveAttribute(
      "aria-expanded",
      "false",
    );
    expect(screen.queryByRole("button", { name: "Research" })).not.toBeInTheDocument();
  });

  it("reuses workspace tree helpers from the lower-level utility module", () => {
    expect(getRootFolderIds(workspaceState.folders)).toEqual(["folder-root"]);
    expect(getFolderAncestorIds(workspaceState.folders, "folder-grandchild")).toEqual([
      "folder-root",
      "folder-child",
    ]);
  });
});
