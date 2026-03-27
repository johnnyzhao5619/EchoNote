import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

const mockNavigate = vi.fn();

vi.mock("@tanstack/react-router", () => ({
  useNavigate: () => mockNavigate,
}));

vi.mock("@/store/workspace", () => ({
  useWorkspaceStore: () => ({
    folders: [
      {
        id: "folder-1",
        name: "Inbox",
        parent_id: null,
        folder_kind: "inbox",
        is_system: true,
        document_count: 2,
        children: [],
      },
    ],
    currentFolderId: null,
    searchQuery: "",
    searchResults: [],
    isSearching: false,
    loadFolderTree: vi.fn(),
    selectFolder: vi.fn(),
    createFolder: vi.fn(),
    renameFolder: vi.fn(),
    deleteFolder: vi.fn(),
    setSearchQuery: vi.fn(),
    search: vi.fn(),
    clearSearch: vi.fn(),
    openDocument: vi.fn(),
  }),
}));

import { WorkspacePanel } from "../WorkspacePanel";

describe("WorkspacePanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders folder tree and create action", async () => {
    render(<WorkspacePanel />);

    expect(await screen.findByText("Inbox")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /新建文件夹/i })).toBeInTheDocument();
  });

  it("navigates to folder route when selecting a folder", async () => {
    render(<WorkspacePanel />);

    fireEvent.click(await screen.findByText("Inbox"));

    expect(mockNavigate).toHaveBeenCalledWith({
      to: "/workspace/$folderId",
      params: { folderId: "folder-1" },
    });
  });
});
