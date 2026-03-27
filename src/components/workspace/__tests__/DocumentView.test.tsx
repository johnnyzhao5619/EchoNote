import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mockExportDocument = vi.fn();
const mockUpdateDocument = vi.fn();
const mockCommands = vi.hoisted(() => ({
  submitLlmTask: vi.fn().mockResolvedValue({ status: "ok", data: "task-1" }),
  cancelLlmTask: vi.fn().mockResolvedValue({ status: "ok", data: null }),
  updateDocumentAsset: vi.fn().mockResolvedValue({ status: "ok", data: null }),
}));

vi.mock("@/store/workspace", () => ({
  useWorkspaceStore: () => ({
    exportDocument: mockExportDocument,
    updateDocument: mockUpdateDocument,
  }),
}));

vi.mock("@/lib/bindings", () => ({
  commands: mockCommands,
}));

vi.mock("@tauri-apps/plugin-dialog", () => ({
  save: vi.fn(),
}));

import { DocumentView } from "../DocumentView";
import { useLlmStore } from "@/store/llm";

describe("DocumentView", () => {
  beforeEach(() => {
    mockExportDocument.mockReset();
    mockUpdateDocument.mockReset();
    mockCommands.submitLlmTask.mockReset().mockResolvedValue({ status: "ok", data: "task-1" });
    mockCommands.cancelLlmTask.mockReset().mockResolvedValue({ status: "ok", data: null });
    mockCommands.updateDocumentAsset.mockReset().mockResolvedValue({ status: "ok", data: null });
    useLlmStore.setState({
      tasks: new Map(),
    });
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

  it("renders recording documents with transcript as the primary body and keeps document_text editable on the same page", () => {
    const { container } = render(
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
              role: "transcript",
              language: null,
              content: "Transcript body",
              updated_at: 2,
            },
            {
              id: "a2",
              role: "document_text",
              language: null,
              content: "Primary body",
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

    const sections = container.querySelectorAll("section");
    expect(within(sections[0]).getByText("转写原文")).toBeInTheDocument();
    expect(within(sections[0]).getByText("Transcript body")).toBeInTheDocument();
    expect(within(sections[1]).getByText("正文")).toBeInTheDocument();
    expect(within(sections[1]).getByText("Primary body")).toBeInTheDocument();
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

  it("resets ai task state when the document changes", async () => {
    const user = userEvent.setup();
    const firstDoc = {
      id: "doc-5",
      title: "Recording One",
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
          content: "Transcript body",
          updated_at: 2,
        },
      ],
    } as const;
    const nextDoc = {
      ...firstDoc,
      id: "doc-6",
      title: "Recording Two",
    } as const;

    const { rerender } = render(<DocumentView doc={firstDoc as any} />);

    await user.click(screen.getByRole("button", { name: /生成摘要/i }));

    await waitFor(() => {
      expect(mockCommands.submitLlmTask).toHaveBeenCalledTimes(1);
      expect(screen.getByRole("button", { name: /取消/i })).toBeInTheDocument();
    });

    rerender(<DocumentView doc={nextDoc as any} />);

    await waitFor(() => {
      expect(screen.queryByRole("button", { name: /取消/i })).not.toBeInTheDocument();
    });
    expect(screen.getByRole("button", { name: /生成摘要/i })).toBeEnabled();

    await user.click(screen.getByRole("button", { name: /生成摘要/i }));

    await waitFor(() => {
      expect(mockCommands.submitLlmTask).toHaveBeenCalledTimes(2);
    });
    expect(mockCommands.submitLlmTask).toHaveBeenLastCalledWith(
      expect.objectContaining({ document_id: "doc-6" }),
    );
  });
});
