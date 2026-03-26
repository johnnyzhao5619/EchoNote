// src/store/models.ts

import { create } from 'zustand'
import { listen } from '@tauri-apps/api/event'
import { commands } from '@/lib/bindings'
import type { DownloadProgressPayload, ModelVariant } from '@/lib/bindings'

interface DownloadState {
  downloadedBytes: number
  totalBytes: number | null
  speedBps: number
  etaSecs: number | null
}

interface ModelsStore {
  variants: ModelVariant[]
  downloads: Record<string, DownloadState>
  requiredMissing: string[]
  isRequiredDialogOpen: boolean
  lastError: string | null

  loadVariants: () => Promise<void>
  startDownload: (variantId: string) => Promise<void>
  cancelDownload: (variantId: string) => Promise<void>
  deleteModel: (variantId: string) => Promise<void>
  setActive: (variantId: string) => Promise<void>
  dismissRequiredDialog: () => void
  clearError: () => void

  _setupListeners: () => () => void
}

export const useModelsStore = create<ModelsStore>((set, get) => ({
  variants: [],
  downloads: {},
  requiredMissing: [],
  isRequiredDialogOpen: false,
  lastError: null,

  loadVariants: async () => {
    const result = await commands.listModelVariants()
    if (result.status === 'ok') {
      set({ variants: result.data })
    } else {
      console.error('[models] loadVariants error:', result.error)
    }
  },

  startDownload: async (variantId) => {
    set((s) => ({
      lastError: null,
      downloads: {
        ...s.downloads,
        [variantId]: { downloadedBytes: 0, totalBytes: null, speedBps: 0, etaSecs: null },
      },
    }))
    const result = await commands.downloadModel(variantId)
    if (result.status === 'error') {
      // Synchronous command error (e.g. channel closed)
      set((s) => {
        const d = { ...s.downloads }
        delete d[variantId]
        return { downloads: d, lastError: String(result.error) }
      })
    }
  },

  cancelDownload: async (variantId) => {
    await commands.cancelDownload(variantId)
    set((s) => {
      const d = { ...s.downloads }
      delete d[variantId]
      return { downloads: d }
    })
  },

  deleteModel: async (variantId) => {
    const result = await commands.deleteModel(variantId)
    if (result.status === 'error') throw new Error(String(result.error))
    await get().loadVariants()
  },

  setActive: async (variantId) => {
    const result = await commands.setActiveModel(variantId)
    if (result.status === 'error') throw new Error(String(result.error))
    await get().loadVariants()
  },

  dismissRequiredDialog: () => set({ isRequiredDialogOpen: false }),
  clearError: () => set({ lastError: null }),

  _setupListeners: () => {
    const unlisteners: Promise<() => void>[] = []

    unlisteners.push(
      listen<{ missing: string[] }>('models:required', (event) => {
        set({
          requiredMissing: event.payload.missing,
          isRequiredDialogOpen: true,
        })
      }),
    )

    unlisteners.push(
      listen<DownloadProgressPayload>('models:progress', (event) => {
        const payload = event.payload
        set((state) => ({
          downloads: {
            ...state.downloads,
            [payload.variant_id]: {
              downloadedBytes: payload.downloaded_bytes,
              totalBytes: payload.total_bytes ?? null,
              speedBps: payload.speed_bps,
              etaSecs: payload.eta_secs ?? null,
            },
          },
        }))
      }),
    )

    unlisteners.push(
      listen<{ variant_id: string }>('models:downloaded', (event) => {
        set((state) => {
          const downloads = { ...state.downloads }
          delete downloads[event.payload.variant_id]
          return { downloads }
        })
        void get().loadVariants()
      }),
    )

    unlisteners.push(
      listen<{ variant_id: string; error: string }>('models:error', (event) => {
        set((state) => {
          const downloads = { ...state.downloads }
          delete downloads[event.payload.variant_id]
          return {
            downloads,
            lastError: event.payload.error,
          }
        })
      }),
    )

    return () => {
      unlisteners.forEach((promise) => {
        void promise.then((dispose) => dispose())
      })
    }
  },
}))
