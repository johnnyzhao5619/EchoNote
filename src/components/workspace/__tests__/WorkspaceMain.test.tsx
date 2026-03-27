import { describe, expect, it, beforeEach, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { open } from "@tauri-apps/plugin-dialog";

const mockNavigate = vi.fn();
let mockParams: {
  folderId?: string;
  docId?: string;
  documentId?: string;
} = {};

vi.mock("@tanstack/react-router", () => ({
  useNavigate: () => mockNavigate,
  useParams: () => mockParams,
}));

vi.mock("@tauri-apps/plugin-dialog", () => ({
  open: vi.fn(),
}));

const workspaceState = {
  documents: [
    {
      id: "doc-1",
      title: "Launch Notes",
      has_transcript: true,
      has_summary: false,
      has_meeting_brief: false,
      updated_at: 1_710_000_000_000,
    },
  ],
  currentDoc: null,
  currentFolderId: "folder-1",
  selectFolder: vi.fn(),
  openDocument: vi.fn(),
  createDocument: vi.fn().mockResolvedValue("doc-new"),
  importFile: vi.fn(),
};

vi.mock("@/store/workspace", () => ({
  useWorkspaceStore: () => workspaceState,
}));

import { WorkspaceMain } from "../WorkspaceMain";

describe("WorkspaceMain", () => {
  beforeEach(() => {
    mockNavigate.mockReset();
    vi.mocked(open).mockReset();
    mockParams = { folderId: "folder-1" };
    workspaceState.selectFolder.mockReset();
    workspaceState.openDocument.mockReset();
    workspaceState.createDocument.mockReset().mockResolvedValue("doc-new");
    workspaceState.importFile.mockReset();
    workspaceState.documents = [
      {
        id: "doc-1",
        title: "Launch Notes",
        has_transcript: true,
        has_summary: false,
        has_meeting_brief: false,
        updated_at: 1_710_000_000_000,
      },
    ];
    workspaceState.currentDoc = null;
    workspaceState.currentFolderId = "folder-1";
  });

  it("shows a loaded document editor when the route already points at a document", () => {
    mockParams = { folderId: "folder-1", docId: "doc-1" };
    workspaceState.currentDoc = {
      id: "doc-1",
      title: "Launch Notes",
      folder_id: "folder-1",
      source_type: "import",
      recording_id: null,
      created_at: 1,
      updated_at: 1,
      assets: [
        {
          id: "asset-1",
          role: "document_text",
          language: null,
          content: "Imported body",
          updated_at: 1,
        },
      ],
    } as any;

    render(<WorkspaceMain />);

    expect(screen.getByRole("textbox", { name: /标题/i })).toHaveValue("Launch Notes");
    expect(screen.getByText("Imported body")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /新建文档/i })).not.toBeInTheDocument();
  });

  it("renders the document list actions and metadata badges for the active folder", () => {
    render(<WorkspaceMain />);

    expect(screen.getByRole("button", { name: /新建文档/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /导入文件/i })).toBeInTheDocument();
    expect(screen.getByText("Launch Notes")).toBeInTheDocument();
    expect(screen.getByText("转写")).toBeInTheDocument();
  });

  it("navigates to document route when clicking a document card", () => {
    render(<WorkspaceMain />);

    fireEvent.click(screen.getByText("Launch Notes"));

    expect(mockNavigate).toHaveBeenCalledWith({
      to: "/workspace/$folderId/$docId",
      params: { folderId: "folder-1", docId: "doc-1" },
    });
  });

  it("navigates to the new document detail after creating a document", async () => {
    render(<WorkspaceMain />);

    fireEvent.click(screen.getByRole("button", { name: /新建文档/i }));

    await waitFor(() => {
      expect(workspaceState.createDocument).toHaveBeenCalledWith("新建文档", "folder-1");
      expect(mockNavigate).toHaveBeenCalledWith({
        to: "/workspace/$folderId/$docId",
        params: { folderId: "folder-1", docId: "doc-new" },
      });
    });
  });

  it("opens the imported document route after a successful import", async () => {
    vi.mocked(open).mockResolvedValue("/tmp/Imported Draft.md");
    workspaceState.importFile.mockResolvedValue({
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
    });

    render(<WorkspaceMain />);

    fireEvent.click(screen.getByRole("button", { name: /导入文件/i }));

    await waitFor(() => {
      expect(workspaceState.importFile).toHaveBeenCalledWith("/tmp/Imported Draft.md", "folder-1");
    });

    expect(mockNavigate).toHaveBeenCalledWith({
      to: "/workspace/$folderId/$docId",
      params: { folderId: "folder-1", docId: "doc-imported" },
    });
  });
});
