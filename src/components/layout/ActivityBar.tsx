import { Link, useRouterState } from "@tanstack/react-router";
import { cn } from "@/lib/utils";
import {
  Mic,
  FileText,
  FolderOpen,
  CalendarDays,
  Settings,
} from "lucide-react";

interface NavItem {
  to: string;
  icon: React.ComponentType<{ className?: string }>;
  label: string;
}

const NAV_ITEMS: NavItem[] = [
  { to: "/recording",      icon: Mic,          label: "Recording" },
  { to: "/transcription",  icon: FileText,      label: "Transcription" },
  { to: "/workspace",      icon: FolderOpen,    label: "Workspace" },
  { to: "/timeline",       icon: CalendarDays,  label: "Timeline" },
];

export function ActivityBar() {
  const { location } = useRouterState();

  return (
    <nav
      aria-label="Activity bar"
      className="flex flex-col items-center justify-between h-full bg-bg-sidebar border-r border-border-default"
      style={{ width: "var(--activity-bar-width)", minWidth: "var(--activity-bar-width)" }}
    >
      {/* 主导航图标 */}
      <div className="flex flex-col items-center gap-1 pt-2">
        {NAV_ITEMS.map(({ to, icon: Icon, label }) => {
          const isActive = location.pathname.startsWith(to);
          return (
            <Link
              key={to}
              to={to}
              aria-label={label}
              title={label}
              className={cn(
                "flex items-center justify-center w-10 h-10 rounded-md transition-colors",
                "text-text-secondary hover:text-text-primary hover:bg-bg-hover",
                isActive && "text-accent border-l-2 border-accent bg-bg-hover"
              )}
            >
              <Icon className="w-5 h-5" />
            </Link>
          );
        })}
      </div>

      {/* 底部设置图标 */}
      <div className="pb-2">
        <Link
          to="/settings"
          aria-label="Settings"
          title="Settings"
          className={cn(
            "flex items-center justify-center w-10 h-10 rounded-md transition-colors",
            "text-text-secondary hover:text-text-primary hover:bg-bg-hover",
            location.pathname.startsWith("/settings") && "text-accent"
          )}
        >
          <Settings className="w-5 h-5" />
        </Link>
      </div>
    </nav>
  );
}
