import { describe, it, expect, beforeEach } from "vitest";
import { act, renderHook } from "@testing-library/react";
import { useThemeStore } from "../theme";

describe("useThemeStore", () => {
  beforeEach(() => {
    // 重置 store 到初始状态
    useThemeStore.setState({
      currentTheme: "Tokyo Night",
      themes: [],
    });
  });

  it("has default theme Tokyo Night", () => {
    const { result } = renderHook(() => useThemeStore());
    expect(result.current.currentTheme).toBe("Tokyo Night");
  });

  it("setTheme updates currentTheme", () => {
    const { result } = renderHook(() => useThemeStore());
    act(() => {
      result.current.setTheme("Tokyo Night Storm");
    });
    expect(result.current.currentTheme).toBe("Tokyo Night Storm");
  });
});
