import { create } from 'zustand'

/**
 * Zustand 全局 UI 状态 Store
 *
 * 原则：只放 UI 状态，不放服务器数据。
 * 服务器数据全走 TanStack Query，避免双数据源同步问题。
 */
interface AppState {
  sidebarOpen: boolean
  toggleSidebar: () => void
  setSidebarOpen: (open: boolean) => void
}

export const useAppStore = create<AppState>((set) => ({
  sidebarOpen: true,
  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
  setSidebarOpen: (open) => set({ sidebarOpen: open }),
}))
