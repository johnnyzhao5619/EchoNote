import { describe, it, expect, beforeEach } from "vitest";
import { render } from "@testing-library/react";
import { ThemeProvider } from "../ThemeProvider";
import { useThemeStore } from "@/store/theme";
import { act } from "react";

describe("ThemeProvider", () => {
  const BUILTIN_THEMES = [
    { name: "Tokyo Night",       type: "dark"  as const },
    { name: "Tokyo Night Storm", type: "dark"  as const },
    { name: "Tokyo Night Light", type: "light" as const },
  ];

  beforeEach(() => {
    useThemeStore.setState({ currentTheme: "Tokyo Night", themes: BUILTIN_THEMES });
    document.documentElement.removeAttribute("data-theme");
    document.documentElement.removeAttribute("data-theme-type");
  });

  it("sets data-theme on mount", () => {
    render(<ThemeProvider><div /></ThemeProvider>);
    expect(document.documentElement.getAttribute("data-theme"))
      .toBe("tokyo-night");
  });

  it("sets data-theme-type dark for Tokyo Night", () => {
    render(<ThemeProvider><div /></ThemeProvider>);
    expect(document.documentElement.getAttribute("data-theme-type"))
      .toBe("dark");
  });

  it("updates data-theme when store changes", () => {
    render(<ThemeProvider><div /></ThemeProvider>);
    act(() => {
      useThemeStore.getState().setTheme("Tokyo Night Light");
    });
    expect(document.documentElement.getAttribute("data-theme"))
      .toBe("tokyo-night-light");
    expect(document.documentElement.getAttribute("data-theme-type"))
      .toBe("light");
  });
});
