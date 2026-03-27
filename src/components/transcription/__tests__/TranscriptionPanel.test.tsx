import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { open } from "@tauri-apps/plugin-dialog";
import { getCurrentWindow } from "@tauri-apps/api/window";

const addFiles = vi.fn();

vi.mock("@tauri-apps/plugin-dialog", () => ({
  open: vi.fn(),
}));

const onDragDropEvent = vi.fn();

vi.mock("@tauri-apps/api/window", () => ({
  getCurrentWindow: vi.fn(() => ({
    onDragDropEvent,
  })),
}));

vi.mock("@/store/transcription", () => ({
  useTranscriptionStore: (selector: (state: unknown) => unknown) =>
    selector({
      addFiles,
      ffmpegAvailable: true,
    }),
}));

import { TranscriptionPanel } from "../TranscriptionPanel";

describe("TranscriptionPanel", () => {
  beforeEach(() => {
    addFiles.mockReset();
    vi.mocked(open).mockReset();
    onDragDropEvent.mockReset().mockResolvedValue(() => {});
  });

  it("adds selected files from the dialog", async () => {
    vi.mocked(open).mockResolvedValue([
      "/tmp/meeting-a.wav",
      "/tmp/meeting-b.mp3",
    ]);

    render(<TranscriptionPanel />);

    fireEvent.click(screen.getByRole("button", { name: /选择文件/i }));

    await waitFor(() => {
      expect(addFiles).toHaveBeenCalledWith([
        "/tmp/meeting-a.wav",
        "/tmp/meeting-b.mp3",
      ]);
    });
  });

  it("subscribes to tauri native drag-drop events and forwards dropped paths", async () => {
    render(<TranscriptionPanel />);

    expect(getCurrentWindow).toHaveBeenCalled();
    expect(onDragDropEvent).toHaveBeenCalledTimes(1);

    const handler = onDragDropEvent.mock.calls[0]?.[0];
    expect(typeof handler).toBe("function");

    await handler({
      payload: {
        type: "drop",
        paths: ["/tmp/drop-a.wav", "/tmp/drop-b.m4a"],
        position: { x: 0, y: 0 },
      },
    });

    await waitFor(() => {
      expect(addFiles).toHaveBeenCalledWith([
        "/tmp/drop-a.wav",
        "/tmp/drop-b.m4a",
      ]);
    });
  });
});
