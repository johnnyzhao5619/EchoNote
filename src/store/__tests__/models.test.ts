import { describe, it, expect, beforeEach, vi } from "vitest";
import { act } from "@testing-library/react";

const { listenerMap, unlisten, mockCommands } = vi.hoisted(() => ({
  listenerMap: new Map<string, (event: { payload: any }) => void>(),
  unlisten: vi.fn(),
  mockCommands: {
    listModelVariants: vi.fn(),
    downloadModel: vi.fn(),
    cancelDownload: vi.fn(),
    deleteModel: vi.fn(),
    setActiveModel: vi.fn(),
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

import { useModelsStore } from "../models";

describe("useModelsStore", () => {
  beforeEach(() => {
    listenerMap.clear();
    unlisten.mockClear();
    Object.values(mockCommands).forEach((fn) => fn.mockReset());
    mockCommands.listModelVariants.mockResolvedValue({ status: "ok", data: [] });

    useModelsStore.setState({
      variants: [],
      downloads: {},
      requiredMissing: [],
      isRequiredDialogOpen: false,
      lastError: null,
    });
  });

  it("setupListeners_opens_required_dialog_on_models_required", async () => {
    const cleanup = useModelsStore.getState()._setupListeners();

    await act(async () => {
      listenerMap.get("models:required")?.({
        payload: { missing: ["whisper/base", "llm/qwen2.5-3b-q4"] },
      });
    });

    const state = useModelsStore.getState();
    expect(state.requiredMissing).toEqual([
      "whisper/base",
      "llm/qwen2.5-3b-q4",
    ]);
    expect(state.isRequiredDialogOpen).toBe(true);

    cleanup();
  });

  it("setupListeners_updates_download_progress_on_models_progress", async () => {
    useModelsStore.getState()._setupListeners();

    await act(async () => {
      listenerMap.get("models:progress")?.({
        payload: {
          variant_id: "whisper/base",
          downloaded_bytes: 512,
          total_bytes: 1024,
          speed_bps: 256,
          eta_secs: 2,
        },
      });
    });

    expect(useModelsStore.getState().downloads["whisper/base"]).toEqual({
      downloadedBytes: 512,
      totalBytes: 1024,
      speedBps: 256,
      etaSecs: 2,
    });
  });

  it("setupListeners_clears_download_and_refreshes_variants_on_models_downloaded", async () => {
    mockCommands.listModelVariants.mockResolvedValue({
      status: "ok",
      data: [
        {
          variant_id: "whisper/base",
          model_type: "whisper",
          name: "base",
          description: "test",
          size_bytes: 100,
          size_display: "100 B",
          is_downloaded: true,
          is_active: true,
          sha256_valid: true,
        },
      ],
    });

    useModelsStore.setState({
      downloads: {
        "whisper/base": {
          downloadedBytes: 10,
          totalBytes: 100,
          speedBps: 5,
          etaSecs: 18,
        },
      },
    });

    useModelsStore.getState()._setupListeners();

    await act(async () => {
      listenerMap.get("models:downloaded")?.({
        payload: { variant_id: "whisper/base" },
      });
      await Promise.resolve();
    });

    expect(useModelsStore.getState().downloads["whisper/base"]).toBeUndefined();
    expect(mockCommands.listModelVariants).toHaveBeenCalledTimes(1);
    expect(useModelsStore.getState().variants).toHaveLength(1);
  });

  it("setupListeners_clears_download_and_sets_error_on_models_error", async () => {
    useModelsStore.setState({
      downloads: {
        "whisper/base": {
          downloadedBytes: 10,
          totalBytes: 100,
          speedBps: 5,
          etaSecs: 18,
        },
      },
    });

    useModelsStore.getState()._setupListeners();

    await act(async () => {
      listenerMap.get("models:error")?.({
        payload: { variant_id: "whisper/base", error: "network failed" },
      });
    });

    expect(useModelsStore.getState().downloads["whisper/base"]).toBeUndefined();
    expect(useModelsStore.getState().lastError).toBe("network failed");
  });
});
