import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

const mockExportDocument = vi.fn();
const mockUpdateDocument = vi.fn();

vi.mock("@/store/workspace", () => ({
  useWorkspaceStore: () => ({
    exportDocument: mockExportDocument,
    updateDocument: mockUpdateDocument,
  }),
}));

vi.mock("@tauri-apps/plugin-dialog", () => ({
  save: vi.fn(),
}));

import { DocumentView } from "../DocumentView";

describe("DocumentView", () => {
  beforeEach(() => {
    mockExportDocument.mockReset();
    mockUpdateDocument.mockReset();
  });

  it("renders editable sections for non-note documents instead of read-only tabs", () => {
    render(
      <DocumentView
        doc={{
          id: "doc-1",
          title: "Weekly Sync",
          folder_id: null,
          source_type: "recording",
          recording_id: null,
          created_at: 1,
          updated_at: 2,
          assets: [
            {
              id: "a1",
              role: "transcript",
              language: null,
              content: "Hello world",
              updated_at: 2,
            },
            {
              id: "a2",
              role: "summary",
              language: null,
              content: "Summary",
              updated_at: 2,
            },
          ],
        }}
      />,
    );

    expect(screen.getByRole("button", { name: /导出/i })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: /标题/i })).toHaveValue("Weekly Sync");
    expect(screen.getByText("转写原文")).toBeInTheDocument();
    expect(screen.getByText("AI 摘要")).toBeInTheDocument();
    expect(screen.queryByRole("tab")).not.toBeInTheDocument();
  });

  it("submits the edited title on blur", async () => {
    render(
      <DocumentView
        doc={{
          id: "doc-2",
          title: "Draft Note",
          folder_id: null,
          source_type: "note",
          recording_id: null,
          created_at: 1,
          updated_at: 2,
          assets: [],
        }}
      />,
    );

    const title = screen.getByRole("textbox", { name: /标题/i });
    fireEvent.change(title, { target: { value: "Renamed Note" } });
    fireEvent.blur(title);

    await waitFor(() => {
      expect(mockUpdateDocument).toHaveBeenCalledWith("doc-2", { title: "Renamed Note" });
    });
  });

  it("opens note documents in an editable body flow instead of a read-only empty state", () => {
    const { container } = render(
      <DocumentView
        doc={{
          id: "doc-2",
          title: "Draft Note",
          folder_id: null,
          source_type: "note",
          recording_id: null,
          created_at: 1,
          updated_at: 2,
          assets: [
            {
              id: "a1",
              role: "document_text",
              language: null,
              content: "Start writing here",
              updated_at: 2,
            },
          ],
        }}
      />,
    );

    expect(screen.getByRole("button", { name: /导出/i })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: /标题/i })).toHaveValue("Draft Note");
    expect(screen.getByRole("button", { name: /编辑正文/i })).toBeInTheDocument();
    expect(screen.queryByText("此文档暂无内容")).not.toBeInTheDocument();
    expect(container.querySelector("pre")).not.toBeInTheDocument();
  });
});
