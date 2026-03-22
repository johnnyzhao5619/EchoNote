import { ActivityBar } from "./ActivityBar";
import { SecondPanel } from "./SecondPanel";
import { TopBar } from "./TopBar";
import { StatusBar } from "./StatusBar";
import { useShellStore } from "@/store/shell";
import { useLlmStream } from "@/hooks/useLlmStream";

interface ShellProps {
  children: React.ReactNode;
}

/**
 * Shell — 应用顶层布局骨架。
 *
 * 布局结构（对标 Obsidian/AnythingLLM）：
 * ┌──────┬────────────────────────────────────┐
 * │  AB  │  TopBar                            │
 * │      ├──────────┬─────────────────────────┤
 * │      │  Second  │  MainContent (children) │
 * │      │  Panel   │                         │
 * │      ├──────────┴─────────────────────────┤
 * │      │  StatusBar                         │
 * └──────┴────────────────────────────────────┘
 *
 * AB = ActivityBar（固定宽度 48px）
 * SecondPanel（可拖拽 160-480px）
 * MainContent = 路由出口（flex-1，占满剩余空间）
 */
export function Shell({ children }: ShellProps) {
  const secondPanelContent = useShellStore((s) => s.secondPanelContent);
  useLlmStream();
  return (
    <div className="flex h-screen overflow-hidden bg-bg-primary text-text-primary">
      {/* 左侧活动栏（固定宽度） */}
      <ActivityBar />

      {/* 右侧主区域（纵向分为 TopBar + 内容区 + StatusBar） */}
      <div className="flex flex-1 flex-col min-w-0 overflow-hidden">
        {/* 顶部操作栏 */}
        <TopBar />

        {/* 中部内容区（SecondPanel + MainContent 并排） */}
        <div className="flex flex-1 min-h-0 overflow-hidden">
          {/* 可调宽二级面板（内容由各路由通过 useShellStore 注入） */}
          <SecondPanel>
            {secondPanelContent}
          </SecondPanel>

          {/* 主内容区：路由出口 */}
          <main className="flex-1 min-w-0 overflow-auto bg-bg-primary">
            {children}
          </main>
        </div>

        {/* 底部状态栏 */}
        <StatusBar />
      </div>
    </div>
  );
}
