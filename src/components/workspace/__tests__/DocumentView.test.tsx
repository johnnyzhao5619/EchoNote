import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

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

  it("renders note documents with document_text as the primary editable body", () => {
    render(
      <DocumentView
        doc={{
          id: "doc-1",
          title: "Weekly Sync",
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
              content: "Note body",
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
    expect(screen.getByText("正文")).toBeInTheDocument();
    expect(screen.getByText("AI 摘要")).toBeInTheDocument();
    expect(screen.getByText("Note body")).toBeInTheDocument();
    expect(screen.queryByText("转写原文")).not.toBeInTheDocument();
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

  it("renders imported documents with document_text as the editable body asset", () => {
    render(
      <DocumentView
        doc={{
          id: "doc-2",
          title: "Draft Note",
          folder_id: null,
          source_type: "import",
          recording_id: null,
          created_at: 1,
          updated_at: 2,
          assets: [
            {
              id: "a1",
              role: "document_text",
              language: null,
              content: "Imported body",
              updated_at: 2,
            },
            {
              id: "a2",
              role: "translation",
              language: "en",
              content: "Imported translation",
              updated_at: 2,
            },
          ],
        }}
      />,
    );

    expect(screen.getByRole("button", { name: /导出/i })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: /标题/i })).toHaveValue("Draft Note");
    expect(screen.getByRole("button", { name: /编辑正文/i })).toBeInTheDocument();
    expect(screen.getByText("正文")).toBeInTheDocument();
    expect(screen.getByText("翻译")).toBeInTheDocument();
    expect(screen.getByText("Imported body")).toBeInTheDocument();
    expect(screen.getByText("Imported translation")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /生成摘要/i })).toBeInTheDocument();
  });

  it("renders recording documents with document_text ahead of transcript when both exist", () => {
    render(
      <DocumentView
        doc={{
          id: "doc-4",
          title: "Recording",
          folder_id: null,
          source_type: "recording",
          recording_id: null,
          created_at: 1,
          updated_at: 2,
          assets: [
            {
              id: "a1",
              role: "document_text",
              language: null,
              content: "Primary body",
              updated_at: 2,
            },
            {
              id: "a2",
              role: "transcript",
              language: null,
              content: "Transcript body",
              updated_at: 2,
            },
            {
              id: "a3",
              role: "summary",
              language: null,
              content: "Summary",
              updated_at: 2,
            },
            {
              id: "a4",
              role: "meeting_brief",
              language: null,
              content: "Brief",
              updated_at: 2,
            },
            {
              id: "a5",
              role: "translation",
              language: "en",
              content: "Translated body",
              updated_at: 2,
            },
          ],
        }}
      />,
    );

    expect(screen.getByText("正文")).toBeInTheDocument();
    expect(screen.getByText("Primary body")).toBeInTheDocument();
    expect(screen.getByText("转写原文")).toBeInTheDocument();
    expect(screen.getByText("Transcript body")).toBeInTheDocument();
    expect(screen.getByText("AI 摘要")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /编辑纪要/i })).toBeInTheDocument();
    expect(screen.getByText("翻译")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /生成摘要/i })).toBeInTheDocument();
  });

  it("shows an actionable empty body state when a document has no editable assets", async () => {
    const user = userEvent.setup();

    render(
      <DocumentView
        doc={{
          id: "doc-3",
          title: "Blank Note",
          folder_id: null,
          source_type: "note",
          recording_id: null,
          created_at: 1,
          updated_at: 2,
          assets: [],
        }}
      />,
    );

    expect(screen.getByRole("button", { name: /编辑正文/i })).toBeInTheDocument();
    expect(screen.getByText("点击开始编写")).toBeInTheDocument();

    await user.click(screen.getByText("点击开始编写"));

    expect(screen.getByRole("textbox", { name: /标题/i })).toHaveValue("Blank Note");
    expect(screen.getByRole("button", { name: /完成/i })).toBeInTheDocument();
    expect(screen.getByPlaceholderText("在此输入正文")).toHaveValue("");
  });
});
