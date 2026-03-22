// src/components/ui/StreamingText.tsx
// 逐字追加渲染流式文本。
// 通过 className prop 保持主题一致性；使用 whitespace-pre-wrap 保留换行。

import { useEffect, useRef } from "react";
import { cn } from "@/lib/utils";

interface StreamingTextProps {
  /** 已接收的 token 列表（来自 useLlmStore）*/
  tokens: string[];
  /** 任务是否已结束（done / failed / cancelled）*/
  isFinished: boolean;
  className?: string;
}

export function StreamingText({
  tokens,
  isFinished,
  className,
}: StreamingTextProps) {
  const endRef = useRef<HTMLDivElement>(null);

  // 每次新 token 到来，自动滚动到底部
  useEffect(() => {
    if (!isFinished) {
      endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
    }
  }, [tokens.length, isFinished]);

  const text = tokens.join("");

  return (
    <div
      className={cn(
        "whitespace-pre-wrap break-words text-text-primary text-sm leading-relaxed",
        className
      )}
    >
      {text}
      {/* 光标动画：推理进行中显示闪烁光标 */}
      {!isFinished && text.length > 0 && (
        <span
          className="inline-block w-0.5 h-4 bg-accent ml-0.5 align-middle animate-pulse"
          aria-hidden="true"
        />
      )}
      <div ref={endRef} />
    </div>
  );
}
