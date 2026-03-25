import { ref, watch } from 'vue'
import type { ThemeMode } from '../types'

const STORAGE_KEY = 'research-lab-theme'

function getInitialTheme(): ThemeMode {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored === 'light' || stored === 'dark') return stored
  } catch { /* ignore */ }
  // Default to dark
  return 'dark'
}

const theme = ref<ThemeMode>(getInitialTheme())

function applyTheme(mode: ThemeMode) {
  document.documentElement.setAttribute('data-theme', mode)
}

// Apply immediately on module load
applyTheme(theme.value)

watch(theme, (mode) => {
  applyTheme(mode)
  try {
    localStorage.setItem(STORAGE_KEY, mode)
  } catch { /* ignore */ }
})

function toggleTheme() {
  theme.value = theme.value === 'dark' ? 'light' : 'dark'
}

function setTheme(mode: ThemeMode) {
  theme.value = mode
}

export function useTheme() {
  return {
    theme,
    toggleTheme,
    setTheme,
  }
}
