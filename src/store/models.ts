// src/store/models.ts

import { create } from 'zustand'
import { commands } from '@/lib/bindings'
import type { ModelVariant } from '@/lib/bindings'

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
      const variants = result.data
      // Detect missing active models (replaces unreliable models:required Tauri event)
      const requiredMissing = variants
        .filter((v) => v.is_active && !v.is_downloaded)
        .map((v) => v.variant_id)
      set({
        variants,
        requiredMissing,
        isRequiredDialogOpen: requiredMissing.length > 0,
      })
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
    // Async download errors are caught by the polling loop via get_download_error
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
    // Tauri events unreliable on macOS dev — poll instead.
    // When downloads are active: refresh variants + check for async errors every 2s.
    const pollTimer = setInterval(async () => {
      const { downloads } = get()
      const inProgress = Object.keys(downloads)
      if (inProgress.length === 0) return

      // Refresh variant list to detect completion
      const variantsResult = await commands.listModelVariants()
      if (variantsResult.status !== 'ok') return

      const freshVariants = variantsResult.data
      const newDownloads = { ...get().downloads }

      for (const v of freshVariants) {
        if (newDownloads[v.variant_id] !== undefined && v.is_downloaded) {
          delete newDownloads[v.variant_id]
        }
      }

      // Check for async download errors (pop-once semantics)
      let lastError: string | null = null
      for (const variantId of inProgress) {
        if (newDownloads[variantId] === undefined) continue // already completed above
        const errResult = await commands.getDownloadError(variantId)
        if (errResult.status === 'ok' && errResult.data) {
          delete newDownloads[variantId]
          lastError = errResult.data
        }
      }

      set({
        variants: freshVariants,
        downloads: newDownloads,
        ...(lastError ? { lastError } : {}),
      })
    }, 2000)

    return () => clearInterval(pollTimer)
  },
}))
