/** 主题状态仓库：明/暗主题，并通过 localStorage 持久化。 */

import { create } from 'zustand'

export type ThemeMode = 'light' | 'dark'

interface ThemeState {
  mode: ThemeMode
  toggle: () => void
  setMode: (mode: ThemeMode) => void
}

const STORAGE_KEY = 'quant-trader-theme'

function loadInitial(): ThemeMode {
  const saved = localStorage.getItem(STORAGE_KEY)
  return saved === 'light' ? 'light' : 'dark'
}

export const useThemeStore = create<ThemeState>(set => ({
  mode: loadInitial(),
  toggle: () =>
    set(state => {
      const mode: ThemeMode = state.mode === 'dark' ? 'light' : 'dark'
      localStorage.setItem(STORAGE_KEY, mode)
      document.body.dataset.theme = mode
      return { mode }
    }),
  setMode: mode => {
    localStorage.setItem(STORAGE_KEY, mode)
    document.body.dataset.theme = mode
    set({ mode })
  },
}))

// 模块加载时立即应用主题
document.body.dataset.theme = loadInitial()
