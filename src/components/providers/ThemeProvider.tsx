import { useEffect } from "react";
import { useThemeStore } from "@/store/theme";
import { commands } from "@/lib/bindings";

/** 将主题名称转换为 data-theme 属性值（与 CSS 选择器一致） */
function themeNameToSlug(name: string): string {
  return name.toLowerCase().replace(/\s+/g, "-");
}

interface ThemeProviderProps {
  children: React.ReactNode;
}

/**
 * ThemeProvider — 负责将 currentTheme 同步到 document.documentElement 的
 * data-theme 和 data-theme-type 属性，驱动 CSS 变量切换。
 *
 * 放在组件树最外层（App.tsx），只渲染一次。
 * 启动时从后端拉取可用主题列表和当前主题，确保与 AppConfig 保持一致。
 */
export function ThemeProvider({ children }: ThemeProviderProps) {
  const { currentTheme, themes, registerThemes, setTheme } = useThemeStore();

  // 启动时从后端拉取主题列表和当前主题（后端为单一真实来源）
  useEffect(() => {
    Promise.all([
      commands.listBuiltinThemes(),
      commands.getCurrentTheme(),
    ]).then(([themesResult, currentResult]) => {
      if (themesResult.status === "ok" && Array.isArray(themesResult.data)) {
        registerThemes(themesResult.data.map(t => ({ name: t.name, type: t.type as "dark" | "light" })));
      }
      if (currentResult.status === "ok" && currentResult.data) {
        // 后端存储 Display Name（如 "Tokyo Night"）；若与当前 Zustand 值不同则同步
        if (currentResult.data !== currentTheme) {
          setTheme(currentResult.data);
        }
      }
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // 仅在挂载时执行一次

  // 主题切换：更新 DOM 属性（依赖 currentTheme 和 themes，两者任一变化均重新同步）
  useEffect(() => {
    const root = document.documentElement;
    const slug = themeNameToSlug(currentTheme);
    const themeInfo = themes.find((t) => t.name === currentTheme);

    root.setAttribute("data-theme", slug);
    root.setAttribute("data-theme-type", themeInfo?.type ?? "dark");
  }, [currentTheme, themes]);

  return <>{children}</>;
}
