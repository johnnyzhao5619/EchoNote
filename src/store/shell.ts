import { create } from 'zustand'
import type { ReactNode } from 'react'

interface ShellStore {
  /** 注入到 Shell SecondPanel 的内容；路由 mount 时 set，unmount 时 clear */
  secondPanelContent: ReactNode | null
  setSecondPanelContent: (content: ReactNode | null) => void
}

export const useShellStore = create<ShellStore>((set) => ({
  secondPanelContent: null,
  setSecondPanelContent: (content) => set({ secondPanelContent: content }),
}))
