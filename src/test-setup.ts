import "@testing-library/jest-dom";

// jsdom 不支持 ResizeObserver（Radix UI SelectContent 需要此 API）
global.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}

// Mock Tauri IPC（防止测试环境调用原生 API）
vi.mock("@tauri-apps/api/core", () => ({
  invoke: vi.fn(),
}));

vi.mock("@tauri-apps/api/event", () => ({
  listen: vi.fn(() => Promise.resolve(() => {})),
  emit: vi.fn(),
}));
