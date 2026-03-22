import { create } from 'zustand'
import { listen, type UnlistenFn } from '@tauri-apps/api/event'
import { commands } from '../lib/bindings'
import type {
  AudioDevice,
  RealtimeConfig,
  SegmentPayload,
  RecordingStatus,
} from '../lib/bindings'

interface RecordingStore {
  // State
  status: 'idle' | 'recording' | 'paused'
  sessionId: string | null
  startedAt: number | null
  audioLevel: number          // 0.0–1.0，由轮询 get_audio_level() 更新
  segments: SegmentPayload[]  // 当前会话所有已确认 segments
  devices: AudioDevice[]
  devicesLoading: boolean

  // Actions
  loadDevices: () => Promise<void>
  start: (config: RealtimeConfig) => Promise<void>
  pause: () => Promise<void>
  resume: () => Promise<void>
  stop: () => Promise<string>  // 返回 recording_id
  syncStatus: () => Promise<void>

  // 内部：事件监听器管理
  _unlisteners: UnlistenFn[]
  _setupEventListeners: () => Promise<() => void>
  // 内部：音频电平轮询定时器
  _levelTimer: ReturnType<typeof setInterval> | null
}

/** 将 AppError（tagged union 对象）转换为人类可读的字符串
 *  AppError 序列化为 { kind: "Model", message: "..." } (adjacently tagged)
 */
function appErrorMessage(err: unknown): string {
  if (typeof err === 'string') return err
  if (err && typeof err === 'object') {
    const e = err as Record<string, unknown>
    // adjacently tagged: { kind: "Model", message: "..." }
    if (typeof e.message === 'string' && e.message.length > 0) return e.message
    // fallback: show kind
    if (typeof e.kind === 'string') return e.kind
  }
  return String(err)
}

export const useRecordingStore = create<RecordingStore>((set, get) => ({
  status: 'idle',
  sessionId: null,
  startedAt: null,
  audioLevel: 0,
  segments: [],
  devices: [],
  devicesLoading: false,
  _unlisteners: [],
  _levelTimer: null,

  loadDevices: async () => {
    set({ devicesLoading: true })
    try {
      const result = await commands.listAudioDevices()
      if (result.status === 'ok' && Array.isArray(result.data)) {
        set({ devices: result.data, devicesLoading: false })
      } else {
        if (result.status === 'error') console.error('[recording] loadDevices error:', result.error)
        set({ devicesLoading: false })
      }
    } catch (e) {
      console.error('[recording] loadDevices error:', e)
      set({ devicesLoading: false })
    }
  },

  start: async (config) => {
    const result = await commands.startRealtime(config)
    if (result.status !== 'ok') {
      throw new Error(appErrorMessage(result.error))
    }
    const sessionId = result.data
    set({
      status: 'recording',
      sessionId,
      startedAt: Date.now(),
      segments: [],
      audioLevel: 0,
    })

    // 轮询 get_audio_level()（每 100ms）和 get_realtime_segments()（每 500ms）
    // 使用命令轮询代替 Tauri 事件系统（事件在 macOS dev 模式下无法可靠到达 WebView）
    let tickCount = 0
    const timer = setInterval(async () => {
      const { status, sessionId: currentSession } = get()
      if (status === 'idle') {
        clearInterval(timer)
        set({ _levelTimer: null, audioLevel: 0 })
        return
      }
      tickCount++
      try {
        const r = await commands.getAudioLevel()
        if (r.status === 'ok') {
          set({ audioLevel: r.data })
        }
      } catch {
        // ignore poll errors
      }
      // 每 2 次（200ms）轮询一次 segments
      if (tickCount % 2 === 0 && currentSession) {
        try {
          const r = await commands.getRealtimeSegments(currentSession)
          if (r.status === 'ok' && r.data.length > 0) {
            set({ segments: r.data })
          }
        } catch {
          // ignore poll errors
        }
      }
    }, 100)
    set({ _levelTimer: timer })
  },

  pause: async () => {
    const { sessionId } = get()
    if (!sessionId) return
    await commands.pauseRealtime(sessionId)
    set({ status: 'paused' })
  },

  resume: async () => {
    const { sessionId } = get()
    if (!sessionId) return
    await commands.resumeRealtime(sessionId)
    set({ status: 'recording' })
  },

  stop: async () => {
    const { sessionId, _levelTimer } = get()
    if (!sessionId) throw new Error('no active session')

    const savedSessionId = sessionId

    // 停止轮询
    if (_levelTimer !== null) {
      clearInterval(_levelTimer)
    }
    // Always reset UI state so user is never stuck in recording mode
    set({ status: 'idle', sessionId: null, startedAt: null, _levelTimer: null, audioLevel: 0 })

    const result = await commands.stopRealtime(savedSessionId)
    if (result.status !== 'ok') {
      throw new Error(appErrorMessage(result.error))
    }

    // 最终 segments 轮询：stop_realtime 等待 pipeline flush 完成后 segments_cache 中保留完整结果
    try {
      const r = await commands.getRealtimeSegments(savedSessionId)
      if (r.status === 'ok' && r.data.length > 0) {
        set({ segments: r.data })
      }
    } catch {
      // ignore
    }

    return result.data
  },

  syncStatus: async () => {
    const result = await commands.getRecordingStatus()
    if (result.status !== 'ok') return
    const status = result.data
    if (status.status === 'recording') {
      set({ status: 'recording', sessionId: status.session_id, startedAt: status.started_at })
    } else if (status.status === 'paused') {
      set({ status: 'paused', sessionId: status.session_id })
    } else {
      set({ status: 'idle', sessionId: null })
    }
  },

  _setupEventListeners: async () => {
    // audio:level 已改用命令轮询，此处只保留 transcription 相关事件

    const unlisten2 = await listen<SegmentPayload>('transcription:segment', (e) => {
      set((state) => {
        // 若 is_partial，替换同 id 的现有 segment；否则追加
        const existing = state.segments.findIndex((s) => s.id === e.payload.id)
        if (existing >= 0) {
          const updated = [...state.segments]
          updated[existing] = e.payload
          return { segments: updated }
        }
        return { segments: [...state.segments, e.payload] }
      })
    })

    const unlisten3 = await listen<RecordingStatus>('transcription:status', (e) => {
      const s = e.payload
      if (s.status === 'recording') {
        set({ status: 'recording', sessionId: s.session_id, startedAt: s.started_at })
      } else if (s.status === 'paused') {
        set({ status: 'paused', sessionId: s.session_id })
      } else if (s.status === 'idle') {
        set({ status: 'idle', sessionId: null })
      }
    })

    const cleanup = () => {
      unlisten2(); unlisten3()
    }
    set({ _unlisteners: [unlisten2, unlisten3] })
    return cleanup
  },
}))
