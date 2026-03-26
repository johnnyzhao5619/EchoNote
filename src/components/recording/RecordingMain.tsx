import { useEffect, useRef, useState, useCallback } from 'react'
import { Button } from '@/components/ui/button'
import { Mic, Pause, Square } from 'lucide-react'
import { useRecordingStore } from '@/store/recording'
import type { RealtimeConfig } from '@/lib/bindings'

function formatDuration(ms: number): string {
  const totalSec = Math.floor(ms / 1000)
  const h = Math.floor(totalSec / 3600)
  const m = Math.floor((totalSec % 3600) / 60)
  const s = totalSec % 60
  return h > 0
    ? `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
    : `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

function AudioWaveform({ level, vadThreshold }: { level: number; vadThreshold?: number }) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  // 保存历史 level 用于波形滚动显示
  const historyRef = useRef<number[]>(new Array(120).fill(0))

  useEffect(() => {
    // 线性增益 10x：iPhone mic RMS≈0.015 → 15%，正常语音 RMS≈0.05 → 50%
    // 不使用 sqrt 放大，避免误导性的高柱（sqrt 在 0.014 时显示为 85%）
    const displayLevel = Math.min(1, level * 10)
    historyRef.current.push(displayLevel)
    if (historyRef.current.length > 120) historyRef.current.shift()

    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const { width, height } = canvas
    ctx.clearRect(0, 0, width, height)

    const barWidth = width / historyRef.current.length
    const accentColor = getComputedStyle(document.documentElement)
      .getPropertyValue('--color-accent-primary').trim() || '#7aa2f7'

    historyRef.current.forEach((lvl, i) => {
      const barHeight = Math.max(2, lvl * height * 0.9)
      const x = i * barWidth
      const y = (height - barHeight) / 2
      ctx.fillStyle = accentColor
      ctx.globalAlpha = 0.4 + lvl * 0.6
      ctx.fillRect(x, y, barWidth - 1, barHeight)
    })
    ctx.globalAlpha = 1

    // VAD 阈值参考线（虚线，显示 adaptive threshold 对应的柱高位置）
    if (vadThreshold !== undefined && vadThreshold > 0) {
      const thresholdDisplayLevel = Math.min(1, vadThreshold * 10)
      const thresholdY = height - thresholdDisplayLevel * height * 0.9
      ctx.save()
      ctx.strokeStyle = '#f7768e'
      ctx.globalAlpha = 0.5
      ctx.setLineDash([4, 4])
      ctx.lineWidth = 1
      ctx.beginPath()
      ctx.moveTo(0, thresholdY)
      ctx.lineTo(width, thresholdY)
      ctx.stroke()
      ctx.restore()
    }
  }, [level, vadThreshold])

  return (
    <canvas
      ref={canvasRef}
      width={480}
      height={80}
      className="w-full rounded-md bg-bg-secondary"
    />
  )
}

interface RecordingMainProps {
  config?: RealtimeConfig
}

export function RecordingMain({ config }: RecordingMainProps) {
  const { status, startedAt, audioLevel, segments, start, pause, resume, stop, _setupEventListeners } =
    useRecordingStore()
  const [elapsed, setElapsed] = useState(0)
  const vadThreshold = config?.vad_threshold
  const [error, setError] = useState<string | null>(null)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const segmentsEndRef = useRef<HTMLDivElement>(null)

  // 设置 Tauri 事件监听器（仅一次）
  useEffect(() => {
    let cleanup: (() => void) | undefined
    _setupEventListeners().then((fn) => { cleanup = fn })
    return () => { cleanup?.() }
  }, [_setupEventListeners])

  // 录音计时器
  useEffect(() => {
    if (status === 'recording' && startedAt) {
      timerRef.current = setInterval(() => {
        setElapsed(Date.now() - startedAt)
      }, 100)
    } else {
      if (timerRef.current) clearInterval(timerRef.current)
      if (status === 'idle') setElapsed(0)
    }
    return () => { if (timerRef.current) clearInterval(timerRef.current) }
  }, [status, startedAt])

  // 字幕自动滚动到底部
  useEffect(() => {
    segmentsEndRef.current?.scrollIntoView?.({ behavior: 'smooth' })
  }, [segments])

  const handleStart = useCallback(async () => {
    if (!config) return
    setError(null)
    try {
      await start(config)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }, [start, config])

  const handleStop = useCallback(async () => {
    // Status is reset to idle immediately in store.stop() before the command returns
    try {
      const recordingId = await stop()
      console.log('[recording] saved as', recordingId)
      setError(null)
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e)
      console.error('[recording] stop error:', msg)
      setError(`Stop failed: ${msg}`)
    }
  }, [stop])

  return (
    <div className="flex flex-col h-full p-6 gap-6">
      {/* 错误提示 */}
      {error && (
        <div className="rounded-md bg-red-500/10 border border-red-500/30 px-3 py-2 text-xs text-red-400">
          {error}
        </div>
      )}
        {/* 控制区 */}
        <div className="flex items-center gap-4">
          {status === 'idle' && (
          <Button onClick={handleStart} className="gap-2" disabled={!config}>
              <Mic className="w-4 h-4" />
              {config ? 'Start Recording' : 'Loading Controls...'}
            </Button>
          )}
        {status === 'recording' && (
          <>
            <Button variant="outline" onClick={() => pause()} className="gap-2">
              <Pause className="w-4 h-4" />
              Pause
            </Button>
            <Button variant="destructive" onClick={handleStop} className="gap-2">
              <Square className="w-4 h-4" />
              Stop
            </Button>
          </>
        )}
        {status === 'paused' && (
          <>
            <Button onClick={() => resume()} className="gap-2">
              <Mic className="w-4 h-4" />
              Resume
            </Button>
            <Button variant="destructive" onClick={handleStop} className="gap-2">
              <Square className="w-4 h-4" />
              Stop
            </Button>
          </>
        )}

        {/* 计时器 */}
        {status !== 'idle' && (
          <div className="flex items-center gap-2 ml-auto">
            {status === 'recording' && (
              <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
            )}
            <span className="font-mono text-lg text-text-primary tabular-nums">
              {formatDuration(elapsed)}
            </span>
          </div>
        )}
      </div>

      {/* 音频波形 Canvas + 实时电平 */}
      <div className="flex flex-col gap-1">
        <AudioWaveform level={audioLevel} vadThreshold={vadThreshold} />
        {status !== 'idle' && (
          <p className="text-xs text-text-muted text-right font-mono">
            level: {audioLevel.toFixed(4)}
          </p>
        )}
      </div>

      {/* 实时字幕 */}
      <div className="flex-1 overflow-y-auto rounded-md bg-bg-secondary p-4 text-sm text-text-primary leading-relaxed">
        {segments.length === 0 ? (
          <p className="text-text-muted text-center mt-8">
            {status === 'recording' && elapsed < 5000
              ? 'Calibrating microphone...'
              : status !== 'idle'
              ? 'Listening...'
              : 'Press Start Recording to begin'}
          </p>
        ) : (
          segments.map((seg) => (
            <span
              key={seg.id}
              className={seg.is_partial ? 'opacity-60' : 'opacity-100'}
            >
              {seg.text}{' '}
            </span>
          ))
        )}
        <div ref={segmentsEndRef} />
      </div>
    </div>
  )
}
