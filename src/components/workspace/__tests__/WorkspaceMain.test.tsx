import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("@tanstack/react-router", () => ({
  useParams: () => ({}),
}));

vi.mock("@tauri-apps/plugin-dialog", () => ({
  open: vi.fn(),
}));

vi.mock("@/store/workspace", () => ({
  useWorkspaceStore: () => ({
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
    createDocument: vi.fn(),
    importFile: vi.fn(),
  }),
}));

import { WorkspaceMain } from "../WorkspaceMain";

describe("WorkspaceMain", () => {
  it("renders document list actions and cards", () => {
    render(<WorkspaceMain />);

    expect(screen.getByRole("button", { name: /新建文档/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /导入文件/i })).toBeInTheDocument();
    expect(screen.getByText("Launch Notes")).toBeInTheDocument();
  });
});
