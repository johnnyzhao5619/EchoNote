import { create } from "zustand";
import { persist } from "zustand/middleware";

/** 主题元信息（不含完整 token 数据） */
export interface ThemeInfo {
  name: string;
  type: "dark" | "light";
}

/** 主题 JSON 文件的 semanticTokens 定义（与 resources/themes/*.json 格式一致） */
export interface ThemeTokens {
  name: string;
  type: "dark" | "light";
  semanticTokens: Record<string, string>;
}

interface ThemeState {
  /** 当前激活主题名称 */
  currentTheme: string;
  /** 已加载的主题元信息列表 */
  themes: ThemeInfo[];
  /** 设置当前主题（触发 ThemeProvider 更新 CSS 变量） */
  setTheme: (name: string) => void;
  /** 注册可用主题（由 ThemeProvider 初始化时调用） */
  registerThemes: (themes: ThemeInfo[]) => void;
}

export const useThemeStore = create<ThemeState>()(
  persist(
    (set) => ({
      currentTheme: "Tokyo Night",
      themes: [],
      setTheme: (name) => set({ currentTheme: name }),
      registerThemes: (themes) => set({ themes }),
    }),
    {
      name: "echonote-theme",
      // 只持久化 currentTheme，themes 列表在每次启动时重新加载
      partialize: (state) => ({ currentTheme: state.currentTheme }),
    }
  )
);
