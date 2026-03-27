import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mocks = vi.hoisted(() => ({
  updateDocumentAsset: vi.fn().mockResolvedValue({ status: "ok", data: null }),
}));

vi.mock("@/lib/bindings", () => ({
  commands: {
    updateDocumentAsset: mocks.updateDocumentAsset,
  },
}));

import { EditableAsset } from "../EditableAsset";

describe("EditableAsset", () => {
  beforeEach(() => {
    mocks.updateDocumentAsset.mockReset().mockResolvedValue({ status: "ok", data: null });
  });

  it("enters edit mode from preview click", async () => {
    const user = userEvent.setup();

    render(
      <EditableAsset
        documentId="doc-1"
        role="document_text"
        label="正文"
        actionLabel="编辑正文"
        initialContent="Hello world"
      />,
    );

    await user.click(screen.getByText("Hello world"));

    expect(screen.getByRole("textbox")).toHaveValue("Hello world");
    expect(screen.getByRole("button", { name: /完成/i })).toBeInTheDocument();
  });

  it("stays closed after clicking 完成", async () => {
    const user = userEvent.setup();

    render(
      <EditableAsset
        documentId="doc-1"
        role="document_text"
        label="正文"
        actionLabel="编辑正文"
        initialContent="Hello world"
      />,
    );

    await user.click(screen.getByText("Hello world"));
    await user.type(screen.getByRole("textbox"), "!");
    await user.click(screen.getByRole("button", { name: /完成/i }));

    await waitFor(() => {
      expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
      expect(screen.getByRole("button", { name: /编辑正文/i })).toBeInTheDocument();
      expect(mocks.updateDocumentAsset).toHaveBeenCalledWith("doc-1", "document_text", "Hello world!");
    });
  });
});
