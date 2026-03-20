import { useRef, useState, useCallback, useEffect } from "react";
import { cn } from "@/lib/utils";

interface SecondPanelProps {
  children: React.ReactNode;
  defaultWidth?: number;
  minWidth?: number;
  maxWidth?: number;
  /** 是否允许完全折叠（宽度 = 0） */
  collapsible?: boolean;
}

/**
 * SecondPanel — 可拖拽宽度的次级面板。
 * 用鼠标拖拽右侧分隔线调整宽度；双击分隔线恢复默认宽度。
 */
export function SecondPanel({
  children,
  defaultWidth = 240,
  minWidth = 160,
  maxWidth = 480,
  collapsible = true,
}: SecondPanelProps) {
  const [width, setWidth] = useState(defaultWidth);
  const [isCollapsed, setIsCollapsed] = useState(false);
  const isDragging = useRef(false);
  const startX = useRef(0);
  const startWidth = useRef(0);

  const onMouseDown = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      isDragging.current = true;
      startX.current = e.clientX;
      startWidth.current = width;
      document.body.style.cursor = "col-resize";
      document.body.style.userSelect = "none";
    },
    [width]
  );

  const onDoubleClick = useCallback(() => {
    if (collapsible) {
      setIsCollapsed((prev) => !prev);
    } else {
      setWidth(defaultWidth);
    }
  }, [collapsible, defaultWidth]);

  useEffect(() => {
    const onMouseMove = (e: MouseEvent) => {
      if (!isDragging.current) return;
      const delta = e.clientX - startX.current;
      const newWidth = Math.max(minWidth, Math.min(maxWidth, startWidth.current + delta));
      setWidth(newWidth);
      if (newWidth <= minWidth && collapsible) {
        setIsCollapsed(true);
      } else {
        setIsCollapsed(false);
      }
    };

    const onMouseUp = () => {
      if (!isDragging.current) return;
      isDragging.current = false;
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };

    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", onMouseUp);
    return () => {
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("mouseup", onMouseUp);
    };
  }, [minWidth, maxWidth, collapsible]);

  const panelWidth = isCollapsed ? 0 : width;

  return (
    <div className="relative flex h-full shrink-0">
      {/* 面板内容区 */}
      <div
        className={cn(
          "flex flex-col h-full overflow-hidden bg-bg-secondary border-r border-border-default transition-none",
          isCollapsed && "border-r-0"
        )}
        style={{ width: panelWidth, minWidth: panelWidth }}
        aria-hidden={isCollapsed}
      >
        {children}
      </div>

      {/* 拖拽分隔线 */}
      <div
        role="separator"
        aria-orientation="vertical"
        aria-label="Resize panel"
        className={cn(
          "absolute right-0 top-0 h-full w-1 cursor-col-resize",
          "hover:bg-accent/30 active:bg-accent/50 transition-colors",
          "z-10"
        )}
        style={{ transform: "translateX(50%)" }}
        onMouseDown={onMouseDown}
        onDoubleClick={onDoubleClick}
      />
    </div>
  );
}
