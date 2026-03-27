import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("@/store/workspace", () => ({
  useWorkspaceStore: () => ({
    exportDocument: vi.fn(),
  }),
}));

vi.mock("@tauri-apps/plugin-dialog", () => ({
  save: vi.fn(),
}));

import { DocumentView } from "../DocumentView";

describe("DocumentView", () => {
  it("renders export entry and asset tabs", () => {
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
            { id: "a1", role: "transcript", language: null, content: "Hello world", updated_at: 2 },
            { id: "a2", role: "summary", language: null, content: "Summary", updated_at: 2 },
          ],
        }}
      />,
    );

    expect(screen.getByRole("button", { name: /导出/i })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /转写原文/i })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /AI 摘要/i })).toBeInTheDocument();
  });
});
