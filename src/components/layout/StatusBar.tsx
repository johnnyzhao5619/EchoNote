import { useRecordingStore } from '@/store/recording'

function AudioLevelIndicator() {
  const { audioLevel, status } = useRecordingStore()

  if (status === 'idle') return null

  const bars = 8
  const activeBars = Math.round(audioLevel * bars)

  return (
    <div className="flex items-center gap-1.5" title={`Audio level: ${(audioLevel * 100).toFixed(0)}%`}>
      {status === 'recording' && (
        <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse" />
      )}
      <div className="flex items-end gap-0.5 h-3">
        {Array.from({ length: bars }).map((_, i) => (
          <div
            key={i}
            className={`w-0.5 rounded-sm transition-all duration-75 ${
              i < activeBars ? 'bg-green-400' : 'bg-border-default'
            }`}
            style={{ height: `${25 + (i / bars) * 75}%` }}
          />
        ))}
      </div>
    </div>
  )
}

export function StatusBar() {
  return (
    <footer
      role="contentinfo"
      aria-label="Status bar"
      className="flex items-center justify-between px-3 bg-bg-sidebar border-t border-border-default text-xs text-text-muted shrink-0"
      style={{ height: 'var(--status-bar-height)' }}
    >
      <div className="flex items-center gap-3">
        <span>EchoNote v3.0.0</span>
      </div>
      <div className="flex items-center gap-3">
        <AudioLevelIndicator />
      </div>
    </footer>
  )
}
