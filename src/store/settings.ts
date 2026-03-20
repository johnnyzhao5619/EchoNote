import { create } from 'zustand'
import { invoke } from '@tauri-apps/api/core'

// Mirror of Rust AppConfig — keep in sync with config/schema.rs
// In the final project this will be imported from src/lib/bindings.ts (tauri-specta generated).
export interface AppConfig {
  locale: string
  active_theme: string
  active_whisper_model: string
  active_llm_model: string
  llm_context_size: number
  vault_path: string
  recordings_path: string
  default_recording_mode: string
  default_language: string | null
  default_target_language: string
  vad_threshold: number
  audio_chunk_ms: number
  auto_llm_on_stop: boolean
  default_llm_task: string
}

// PartialAppConfig: every field is optional (undefined = do not update)
export type PartialAppConfig = {
  [K in keyof AppConfig]?: AppConfig[K] | undefined
}

interface SettingsStore {
  config: AppConfig | null
  isLoading: boolean
  error: string | null
  translations: Record<string, unknown>

  // Actions
  loadConfig: () => Promise<void>
  updateConfig: (partial: PartialAppConfig) => Promise<void>
  resetConfig: () => Promise<void>
}

const DEFAULT_CONFIG: AppConfig = {
  locale: 'zh_CN',
  active_theme: 'tokyo-night',
  active_whisper_model: 'whisper/base',
  active_llm_model: 'llm/qwen2.5-3b-q4',
  llm_context_size: 4096,
  vault_path: '',
  recordings_path: '',
  default_recording_mode: 'transcribe_only',
  default_language: null,
  default_target_language: 'en',
  vad_threshold: 0.02,
  audio_chunk_ms: 500,
  auto_llm_on_stop: false,
  default_llm_task: 'summary',
}

export const useSettingsStore = create<SettingsStore>((set) => ({
  config: null,
  isLoading: false,
  error: null,
  translations: {},

  loadConfig: async () => {
    set({ isLoading: true, error: null })
    try {
      const config = await invoke<AppConfig>('get_config')
      set({ config, isLoading: false })
    } catch (e) {
      set({ error: String(e), isLoading: false, config: DEFAULT_CONFIG })
    }
  },

  updateConfig: async (partial: PartialAppConfig) => {
    set({ isLoading: true, error: null })
    try {
      await invoke<void>('update_config', { partial })
      // Optimistically update local state
      set((state) => ({
        config: state.config ? { ...state.config, ...filterUndefined(partial) } : state.config,
        isLoading: false,
      }))
    } catch (e) {
      set({ error: String(e), isLoading: false })
      throw e
    }
  },

  resetConfig: async () => {
    set({ isLoading: true, error: null })
    try {
      const config = await invoke<AppConfig>('reset_config')
      set({ config, isLoading: false })
    } catch (e) {
      set({ error: String(e), isLoading: false })
      throw e
    }
  },
}))

/** Remove keys with `undefined` values before sending to Tauri. */
function filterUndefined<T extends object>(obj: T): Partial<T> {
  return Object.fromEntries(
    Object.entries(obj).filter(([, v]) => v !== undefined)
  ) as Partial<T>
}
