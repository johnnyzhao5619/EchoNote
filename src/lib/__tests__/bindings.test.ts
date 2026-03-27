import { describe, it, expect } from "vitest";

// 验证 bindings.ts 导出预期的命令函数
describe("bindings smoke test", () => {
  it("exports get_current_theme command", async () => {
    const bindings = await import("../bindings");
    expect(typeof bindings.commands.getCurrentTheme).toBe("function");
  });

  it("exports set_current_theme command", async () => {
    const bindings = await import("../bindings");
    expect(typeof bindings.commands.setCurrentTheme).toBe("function");
  });

  it("exports list_builtin_themes command", async () => {
    const bindings = await import("../bindings");
    expect(typeof bindings.commands.listBuiltinThemes).toBe("function");
  });

  it("exports workspace M6 commands", async () => {
    const bindings = await import("../bindings");
    expect(typeof bindings.commands.listFolderTree).toBe("function");
    expect(typeof bindings.commands.createFolder).toBe("function");
    expect(typeof bindings.commands.searchWorkspace).toBe("function");
    expect(typeof bindings.commands.exportDocument).toBe("function");
    expect(typeof bindings.commands.importFileToWorkspace).toBe("function");
  });

  it("exports batch transcription M7 commands", async () => {
    const bindings = await import("../bindings");
    expect(typeof bindings.commands.checkFfmpegAvailable).toBe("function");
    expect(typeof bindings.commands.addFilesToBatch).toBe("function");
    expect(typeof bindings.commands.getBatchQueue).toBe("function");
    expect(typeof bindings.commands.cancelBatchJob).toBe("function");
    expect(typeof bindings.commands.clearCompletedJobs).toBe("function");
  });
});
