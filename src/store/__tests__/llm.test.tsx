import { beforeEach, describe, expect, it, vi } from "vitest";
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const { listenerMap, unlisten, mockCommands } = vi.hoisted(() => ({
  listenerMap: new Map<string, (event: { payload: any }) => void>(),
  unlisten: vi.fn(),
  mockCommands: {
    submitLlmTask: vi.fn(),
    cancelLlmTask: vi.fn(),
  },
}));

vi.mock("@tauri-apps/api/event", () => ({
  listen: vi.fn((eventName: string, callback: (event: { payload: any }) => void) => {
    listenerMap.set(eventName, callback);
    return Promise.resolve(unlisten);
  }),
}));

vi.mock("@/lib/bindings", () => ({
  commands: mockCommands,
}));

import { AiTaskBar } from "@/components/workspace/AiTaskBar";
import { useLlmStream } from "@/hooks/useLlmStream";
import { useLlmStore } from "../llm";

function LlmStreamHost() {
  useLlmStream();
  return null;
}

describe("LLM task lifecycle", () => {
  beforeEach(() => {
    listenerMap.clear();
    unlisten.mockClear();
    mockCommands.submitLlmTask.mockReset();
    mockCommands.cancelLlmTask.mockReset();
    mockCommands.submitLlmTask.mockResolvedValue({ status: "ok", data: "task-1" });
    mockCommands.cancelLlmTask.mockResolvedValue({ status: "ok", data: null });

    useLlmStore.setState({
      tasks: new Map(),
    });
  });

  it("preserves early events that arrive before initTask", async () => {
    render(<LlmStreamHost />);

    await act(async () => {
      await Promise.resolve();
    });

    await act(async () => {
      listenerMap.get("llm:token")?.({
        payload: { task_id: "task-early", token: "会议摘要" },
      });
      listenerMap.get("llm:error")?.({
        payload: {
          task_id: "task-early",
          kind: "failed",
          error: "engine not loaded",
        },
      });
    });

    let task = useLlmStore.getState().tasks.get("task-early");
    expect(task).toMatchObject({
      taskId: "task-early",
      documentId: "",
      status: "failed",
      tokens: ["会议摘要"],
      errorMsg: "engine not loaded",
    });

    act(() => {
      useLlmStore.getState().initTask("task-early", "doc-1");
    });

    task = useLlmStore.getState().tasks.get("task-early");
    expect(task).toMatchObject({
      taskId: "task-early",
      documentId: "doc-1",
      status: "failed",
      tokens: ["会议摘要"],
      errorMsg: "engine not loaded",
    });
  });

  it("re-enables submit actions after receiving a cancelled terminal event", async () => {
    const user = userEvent.setup();

    render(
      <>
        <LlmStreamHost />
        <AiTaskBar documentId="doc-1" />
      </>,
    );

    await act(async () => {
      await Promise.resolve();
    });

    const summaryButton = screen.getByRole("button", { name: /生成摘要/i });
    await user.click(summaryButton);

    await waitFor(() => {
      expect(mockCommands.submitLlmTask).toHaveBeenCalledTimes(1);
      expect(screen.getByRole("button", { name: /取消/i })).toBeInTheDocument();
    });
    expect(summaryButton).toBeDisabled();

    await act(async () => {
      listenerMap.get("llm:error")?.({
        payload: {
          task_id: "task-1",
          kind: "cancelled",
          error: "cancelled",
        },
      });
    });

    await waitFor(() => {
      expect(screen.queryByRole("button", { name: /取消/i })).not.toBeInTheDocument();
    });
    expect(summaryButton).toBeEnabled();
  });

  it("resets the active task when the document changes", async () => {
    const user = userEvent.setup();

    const { rerender } = render(
      <>
        <LlmStreamHost />
        <AiTaskBar documentId="doc-1" />
      </>,
    );

    await act(async () => {
      await Promise.resolve();
    });

    await user.click(screen.getByRole("button", { name: /生成摘要/i }));

    await waitFor(() => {
      expect(mockCommands.submitLlmTask).toHaveBeenCalledTimes(1);
      expect(screen.getByRole("button", { name: /取消/i })).toBeInTheDocument();
    });

    rerender(
      <>
        <LlmStreamHost />
        <AiTaskBar documentId="doc-2" />
      </>,
    );

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
