import { create } from 'zustand'
import { commands, type AppConfig, type AppError, type PartialAppConfig } from '../lib/bindings'

interface SettingsStore {
  config: AppConfig | null
  isLoading: boolean
  error: string | null
  translations: Record<string, unknown>
  loadConfig: () => Promise<void>
  updateConfig: (partial: PartialAppConfig) => Promise<void>
  resetConfig: () => Promise<void>
}

export const useSettingsStore = create<SettingsStore>((set) => ({
  config: null,
  isLoading: false,
  error: null,
  translations: {},

  loadConfig: async () => {
    set({ isLoading: true, error: null })
    const result = await commands.getConfig()
    if (result.status === 'ok') {
      set({ config: result.data, isLoading: false })
      return
    }

    set({ error: formatAppError(result.error), isLoading: false })
  },

  updateConfig: async (partial: PartialAppConfig) => {
    set({ isLoading: true, error: null })
    const cleaned = filterUndefined(partial)
    const result = await commands.updateConfig(cleaned)

    if (result.status === 'ok') {
      set((state) => ({
        config: state.config ? ({ ...state.config, ...cleaned } as AppConfig) : state.config,
        isLoading: false,
      }))
      return
    }

    const error = formatAppError(result.error)
    set({ error, isLoading: false })
    throw new Error(error)
  },

  resetConfig: async () => {
    set({ isLoading: true, error: null })
    const result = await commands.resetConfig()
    if (result.status === 'ok') {
      set({ config: result.data, isLoading: false })
      return
    }

    const error = formatAppError(result.error)
    set({ error, isLoading: false })
    throw new Error(error)
  },
}))

function filterUndefined<T extends object>(obj: T): Partial<T> {
  return Object.fromEntries(
    Object.entries(obj).filter(([, value]) => value !== undefined),
  ) as Partial<T>
}

function formatAppError(error: AppError): string {
  if ('message' in error) {
    return error.message
  }

  return error.kind
}
