import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const { mockCommands } = vi.hoisted(() => ({
  mockCommands: {
    submitLlmTask: vi.fn(),
    cancelLlmTask: vi.fn(),
  },
}));

vi.mock("@/lib/bindings", () => ({
  commands: mockCommands,
}));

import { AiTaskBar } from "../AiTaskBar";
import { useLlmStore } from "@/store/llm";

describe("AiTaskBar", () => {
  beforeEach(() => {
    mockCommands.submitLlmTask.mockReset();
    mockCommands.cancelLlmTask.mockReset();
    mockCommands.submitLlmTask.mockResolvedValue({ status: "ok", data: "task-1" });
    mockCommands.cancelLlmTask.mockResolvedValue({ status: "ok", data: null });

    useLlmStore.setState({
      tasks: new Map(),
    });
  });

  it("resets the active task when the document changes", async () => {
    const user = userEvent.setup();

    const { rerender } = render(<AiTaskBar documentId="doc-1" />);

    await user.click(screen.getByRole("button", { name: /生成摘要/i }));

    await waitFor(() => {
      expect(mockCommands.submitLlmTask).toHaveBeenCalledTimes(1);
      expect(screen.getByRole("button", { name: /取消/i })).toBeInTheDocument();
    });

    rerender(<AiTaskBar documentId="doc-2" />);

    expect(screen.queryByRole("button", { name: /取消/i })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /生成摘要/i })).toBeEnabled();

    await user.click(screen.getByRole("button", { name: /生成摘要/i }));

    await waitFor(() => {
      expect(mockCommands.submitLlmTask).toHaveBeenCalledTimes(2);
    });
    expect(mockCommands.submitLlmTask).toHaveBeenLastCalledWith(
      expect.objectContaining({ document_id: "doc-2" }),
    );
  });
});
