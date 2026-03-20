import { describe, it, expect, vi } from "vitest";

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
});
