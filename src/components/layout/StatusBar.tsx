export function StatusBar() {
  return (
    <footer
      role="contentinfo"
      aria-label="Status bar"
      className="flex items-center justify-between px-3 bg-bg-sidebar border-t border-border-default text-xs text-text-muted shrink-0"
      style={{ height: "var(--status-bar-height)" }}
    >
      <div className="flex items-center gap-3">
        {/* TODO(M2): 模型状态 */}
        <span>EchoNote v3.0.0</span>
      </div>
      <div className="flex items-center gap-3">
        {/* TODO(M2): 音频电平 */}
        {/* TODO(M5): 语言选择 */}
      </div>
    </footer>
  );
}
