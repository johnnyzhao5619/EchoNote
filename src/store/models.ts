// src/store/models.ts

import { create } from 'zustand'
import { invoke } from '@tauri-apps/api/core'
import type { ModelVariant } from '../lib/bindings'

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
  lastError: string | null                  // most recent download error

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
  lastError: null,

  loadVariants: async () => {
    try {
      const variants = await invoke<ModelVariant[]>('list_model_variants')
      set({ variants })
    } catch (e) {
      console.error('[models] loadVariants error:', e)
    }
  },

  startDownload: async (variantId) => {
    // 乐观更新：立即显示进度条（0 bytes），让用户知道下载已触发
    set((s) => ({
      downloads: {
        ...s.downloads,
        [variantId]: { downloadedBytes: 0, totalBytes: null, speedBps: 0, etaSecs: null },
      },
    }))
    try {
      await invoke('download_model', { variantId })
    } catch (e) {
      console.error('[models] startDownload error:', e)
      // 清除乐观状态
      set((s) => {
        const d = { ...s.downloads }
        delete d[variantId]
        return { downloads: d }
      })
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
    // Tauri 事件系统在 macOS 开发模式下不可靠，改用轮询方案。
    // 当有下载进行中时，每 2 秒刷新一次变体列表以检测下载完成状态。
    const pollTimer = setInterval(async () => {
      const { downloads } = get()
      if (Object.keys(downloads).length === 0) return

      try {
        const freshVariants = await invoke<ModelVariant[]>('list_model_variants')
        const newDownloads = { ...get().downloads }
        let anyCompleted = false
        for (const v of freshVariants) {
          if (newDownloads[v.variant_id] !== undefined && v.is_downloaded) {
            delete newDownloads[v.variant_id]
            anyCompleted = true
          }
        }
        if (anyCompleted) {
          set({ variants: freshVariants, downloads: newDownloads })
        } else {
          set({ variants: freshVariants })
        }
      } catch (e) {
        console.error('[models] poll error:', e)
      }
    }, 2000)

    return () => {
      clearInterval(pollTimer)
    }
  },
}))
