import { useEffect } from "react";
import { useThemeStore, type ThemeInfo } from "@/store/theme";

/** 将主题名称转换为 data-theme 属性值（与 CSS 选择器一致） */
function themeNameToSlug(name: string): string {
  return name.toLowerCase().replace(/\s+/g, "-");
}

const BUILTIN_THEMES: ThemeInfo[] = [
  { name: "Tokyo Night",       type: "dark" },
  { name: "Tokyo Night Storm", type: "dark" },
  { name: "Tokyo Night Light", type: "light" },
];

interface ThemeProviderProps {
  children: React.ReactNode;
}

/**
 * ThemeProvider — 负责将 currentTheme 同步到 document.documentElement 的
 * data-theme 和 data-theme-type 属性，驱动 CSS 变量切换。
 *
 * 放在组件树最外层（App.tsx），只渲染一次。
 */
export function ThemeProvider({ children }: ThemeProviderProps) {
  const { currentTheme, registerThemes } = useThemeStore();

  // 初始化：注册内置主题列表
  useEffect(() => {
    registerThemes(BUILTIN_THEMES);
  }, [registerThemes]);

  // 主题切换：更新 DOM 属性
  useEffect(() => {
    const root = document.documentElement;
    const slug = themeNameToSlug(currentTheme);
    const themeInfo = BUILTIN_THEMES.find((t) => t.name === currentTheme);

    root.setAttribute("data-theme", slug);
    root.setAttribute("data-theme-type", themeInfo?.type ?? "dark");
  }, [currentTheme]);

  return <>{children}</>;
}
