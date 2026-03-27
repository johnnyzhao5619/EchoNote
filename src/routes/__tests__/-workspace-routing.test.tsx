import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import {
  RouterProvider,
  createMemoryHistory,
  createRouter,
} from "@tanstack/react-router";

import { routeTree } from "@/routeTree.gen";
import { useWorkspaceStore } from "@/store/workspace";

const mockCommands = vi.hoisted(() => ({
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
}));
const mockDialog = vi.hoisted(() => ({
  open: vi.fn(),
}));

vi.mock("@/lib/bindings", () => ({
  commands: mockCommands,
}));

vi.mock("@tauri-apps/plugin-dialog", () => ({
  open: mockDialog.open,
}));

vi.mock("use-debounce", () => ({
  useDebounce: (value: string) => [value],
}));

const baseTree = [
  {
    id: "folder-root",
    name: "Workspace",
    parent_id: null,
    folder_kind: "workspace",
    is_system: false,
    document_count: 2,
    children: [
      {
        id: "folder-child",
        name: "Project A",
        parent_id: "folder-root",
        folder_kind: "workspace",
        is_system: false,
        document_count: 1,
        children: [],
      },
    ],
  },
];

function renderApp(initialPath = "/workspace") {
  const history = createMemoryHistory({ initialEntries: [initialPath] });
  const router = createRouter({ routeTree, history });
  return render(<RouterProvider router={router} />);
}

describe("workspace routing", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockCommands.listFolderTree.mockResolvedValue({ status: "ok", data: baseTree });
    mockCommands.listDocumentsInFolder.mockResolvedValue({ status: "ok", data: [] });
    mockCommands.getDocument.mockResolvedValue({
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
    });
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

  afterEach(() => {
    vi.useRealTimers();
  });

  it("opens a newly created document in the editor route", async () => {
    mockCommands.createDocument.mockResolvedValueOnce({
      status: "ok",
      data: {
        id: "doc-new",
        title: "新建文档",
        folder_id: "folder-1",
        source_type: "note",
        has_transcript: false,
        has_summary: false,
        has_meeting_brief: false,
        recording_id: null,
        created_at: 1,
        updated_at: 1,
      },
    });
    mockCommands.getDocument.mockResolvedValueOnce({
      status: "ok",
      data: {
        id: "doc-new",
        title: "新建文档",
        folder_id: "folder-1",
        source_type: "note",
        recording_id: null,
        created_at: 1,
        updated_at: 1,
        assets: [
          {
            id: "asset-new",
            role: "document_text",
            language: null,
            content: "",
            updated_at: 1,
          },
        ],
      },
    });

    renderApp("/workspace/folder-1");

    fireEvent.click(await screen.findByRole("button", { name: /新建文档/i }));

    await waitFor(() => {
      expect(mockCommands.createDocument).toHaveBeenCalledWith("新建文档", "folder-1", "");
    });

    await waitFor(() => {
      expect(screen.getByRole("textbox", { name: /标题/i })).toHaveValue("新建文档");
    });
    expect(screen.getByText("点击开始编写")).toBeInTheDocument();
  });

  it("opens an imported document in the editor after file selection", async () => {
    mockCommands.importFileToWorkspace.mockResolvedValueOnce({
      status: "ok",
      data: {
        id: "doc-imported",
        title: "Imported Draft",
        folder_id: "folder-1",
        source_type: "import",
        has_transcript: false,
        has_summary: false,
        has_meeting_brief: false,
        recording_id: null,
        created_at: 1,
        updated_at: 2,
      },
    });
    mockCommands.getDocument.mockResolvedValueOnce({
      status: "ok",
      data: {
        id: "doc-imported",
        title: "Imported Draft",
        folder_id: "folder-1",
        source_type: "import",
        recording_id: null,
        created_at: 1,
        updated_at: 2,
        assets: [
          {
            id: "asset-imported",
            role: "document_text",
            language: null,
            content: "Imported body",
            updated_at: 2,
          },
        ],
      },
    });
    mockDialog.open.mockResolvedValueOnce("/tmp/Imported Draft.md");

    renderApp("/workspace/folder-1");

    fireEvent.click(await screen.findByRole("button", { name: /导入文件/i }));

    await waitFor(() => {
      expect(mockCommands.importFileToWorkspace).toHaveBeenCalledWith("/tmp/Imported Draft.md", "folder-1");
    });

    await waitFor(() => {
      expect(screen.getByRole("textbox", { name: /标题/i })).toHaveValue("Imported Draft");
    });
    expect(screen.getByText("Imported body")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /编辑正文/i })).toBeInTheDocument();
  });

  it("keeps the ancestor chain expanded when navigating from search into a deep document", async () => {
    mockCommands.listFolderTree.mockResolvedValueOnce({
      status: "ok",
      data: [
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
    });
    mockCommands.searchWorkspace.mockResolvedValueOnce({
      status: "ok",
      data: [
        {
          document_id: "doc-search",
          title: "Deep Search Result",
          snippet: "<mark>Deep</mark> search result",
          rank: -1,
          folder_id: "folder-grandchild",
          updated_at: 1,
        },
      ],
    });

    renderApp("/workspace");

    fireEvent.change(await screen.findByPlaceholderText("搜索文档…"), {
      target: { value: "Deep" },
    });

    await waitFor(() => {
      expect(mockCommands.searchWorkspace).toHaveBeenCalledWith("Deep");
    });

    fireEvent.click(await screen.findByText("Deep Search Result"));

    await waitFor(() => {
      expect(screen.getByRole("textbox", { name: /标题/i })).toHaveValue("Launch Notes");
    });
    expect(screen.getByRole("treeitem", { name: "Research" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(screen.getByRole("treeitem", { name: "Research" })).toHaveAttribute(
      "aria-level",
      "3",
    );
    expect(screen.getByRole("button", { name: "折叠 Project A" })).toHaveAttribute(
      "aria-expanded",
      "true",
    );
  });
});
