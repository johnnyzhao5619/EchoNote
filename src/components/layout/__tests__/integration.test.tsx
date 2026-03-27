import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import {
  createMemoryHistory,
  createRouter,
  RouterProvider,
} from "@tanstack/react-router";
import { routeTree } from "../../../routeTree.gen";

// Default AppConfig returned by the mocked invoke in settings tests
const MOCK_APP_CONFIG = {
  locale: "zh_CN",
  active_theme: "Tokyo Night",
  active_whisper_model: "whisper/base",
  active_llm_model: "llm/qwen2.5-3b-q4",
  llm_context_size: 4096,
  vault_path: "/data/vault",
  recordings_path: "/data/recordings",
  default_recording_mode: "transcribe_only",
  default_language: null,
  default_target_language: "en",
  vad_threshold: 0.02,
  auto_llm_on_stop: false,
  default_llm_task: "summary",
  last_used_device_id: null,
  model_mirror: "",
};

function renderApp(initialPath = "/recording") {
  const history = createMemoryHistory({ initialEntries: [initialPath] });
  const router = createRouter({ routeTree, history });
  return render(<RouterProvider router={router} />);
}

describe("M1 Integration: Shell + Router + Theme", () => {
  it("renders full app shell with all layout regions", async () => {
    renderApp();
    await waitFor(() => {
      expect(screen.getByRole("navigation", { name: /activity bar/i }))
        .toBeInTheDocument();
      expect(screen.getByRole("contentinfo"))
        .toBeInTheDocument(); // StatusBar
      expect(screen.getByRole("main"))
        .toBeInTheDocument();  // 主内容区
    });
  });

  it("default route redirects to /recording and shows recording page", async () => {
    renderApp("/");
    await screen.findByRole("button", { name: /start recording/i });
  });

  it("navigating to /workspace shows workspace page", async () => {
    const { invoke } = await import("@tauri-apps/api/core");
    vi.mocked(invoke).mockResolvedValueOnce([]);
    renderApp("/workspace");
    await screen.findByRole("button", { name: /新建文件夹/i });
    expect(screen.getByText(/此文件夹为空/i)).toBeInTheDocument();
  });

  it("navigating to /settings shows settings form", async () => {
    // Make invoke return a valid AppConfig so SettingsMain renders
    const { invoke } = await import("@tauri-apps/api/core");
    vi.mocked(invoke).mockResolvedValueOnce(MOCK_APP_CONFIG);
    renderApp("/settings");
    await screen.findByText(/general settings/i);
  });
});
