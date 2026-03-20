// src/store/models.ts

import { create } from 'zustand'
import { listen } from '@tauri-apps/api/event'
import { invoke } from '@tauri-apps/api/core'
import type { ModelVariant, DownloadProgressPayload } from '../lib/bindings'

interface DownloadState {
  downloadedBytes: number
  totalBytes: number | null
  speedBps: number
  etaSecs: number | null
}

interface ModelsStore {
  variants: ModelVariant[]
  downloads: Record<string, DownloadState> // variant_id → progress
  requiredMissing: string[]                 // from models:required event
  isRequiredDialogOpen: boolean

  // Actions
  loadVariants: () => Promise<void>
  startDownload: (variantId: string) => Promise<void>
  cancelDownload: (variantId: string) => Promise<void>
  deleteModel: (variantId: string) => Promise<void>
  setActive: (variantId: string) => Promise<void>
  dismissRequiredDialog: () => void

  // Internal
  _setupListeners: () => () => void
}

export const useModelsStore = create<ModelsStore>((set, get) => ({
  variants: [],
  downloads: {},
  requiredMissing: [],
  isRequiredDialogOpen: false,

  loadVariants: async () => {
    try {
      const variants = await invoke<ModelVariant[]>('list_model_variants')
      set({ variants })
    } catch (e) {
      console.error('[models] loadVariants error:', e)
    }
  },

  startDownload: async (variantId) => {
    try {
      await invoke('download_model', { variantId })
    } catch (e) {
      console.error('[models] startDownload error:', e)
    }
  },

  cancelDownload: async (variantId) => {
    try {
      await invoke('cancel_download', { variantId })
    } catch (e) {
      console.error('[models] cancelDownload error:', e)
    }
    set((s) => {
      const d = { ...s.downloads }
      delete d[variantId]
      return { downloads: d }
    })
  },

  deleteModel: async (variantId) => {
    try {
      await invoke('delete_model', { variantId })
      await get().loadVariants()
    } catch (e) {
      console.error('[models] deleteModel error:', e)
      throw e
    }
  },

  setActive: async (variantId) => {
    try {
      await invoke('set_active_model', { variantId })
      await get().loadVariants()
    } catch (e) {
      console.error('[models] setActive error:', e)
      throw e
    }
  },

  dismissRequiredDialog: () => set({ isRequiredDialogOpen: false }),

  _setupListeners: () => {
    const unlisteners: Promise<() => void>[] = []

    // models:required → open onboarding dialog
    unlisteners.push(
      listen<{ missing: string[] }>('models:required', (e) => {
        set({ requiredMissing: e.payload.missing, isRequiredDialogOpen: true })
      })
    )

    // models:progress → update download progress
    unlisteners.push(
      listen<DownloadProgressPayload>('models:progress', (e) => {
        const p = e.payload
        set((s) => ({
          downloads: {
            ...s.downloads,
            [p.variant_id]: {
              downloadedBytes: p.downloaded_bytes,
              totalBytes: p.total_bytes ?? null,
              speedBps: p.speed_bps,
              etaSecs: p.eta_secs ?? null,
            },
          },
        }))
      })
    )

    // models:downloaded → refresh list, clear progress
    unlisteners.push(
      listen<{ variant_id: string }>('models:downloaded', (e) => {
        set((s) => {
          const d = { ...s.downloads }
          delete d[e.payload.variant_id]
          return { downloads: d }
        })
        get().loadVariants()
      })
    )

    // models:error → clear progress
    unlisteners.push(
      listen<{ variant_id: string; error: string }>('models:error', (e) => {
        console.error('[models] download error:', e.payload.error)
        set((s) => {
          const d = { ...s.downloads }
          delete d[e.payload.variant_id]
          return { downloads: d }
        })
      })
    )

    return () => {
      unlisteners.forEach((p) => p.then((fn) => fn()))
    }
  },
}))
