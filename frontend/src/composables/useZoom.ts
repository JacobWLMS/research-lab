import { ref, watch } from 'vue'

const STORAGE_KEY = 'research-lab-zoom'
const ZOOM_LEVELS = [80, 90, 100, 110, 120] as const

export type ZoomLevel = (typeof ZOOM_LEVELS)[number]

function getInitialZoom(): ZoomLevel {
  try {
    const stored = Number(localStorage.getItem(STORAGE_KEY))
    if (ZOOM_LEVELS.includes(stored as ZoomLevel)) return stored as ZoomLevel
  } catch { /* ignore */ }
  return 100
}

const zoom = ref<ZoomLevel>(getInitialZoom())

function applyZoom(level: ZoomLevel) {
  document.documentElement.style.fontSize = `${(level / 100) * 14}px`
}

// Apply immediately
applyZoom(zoom.value)

watch(zoom, (level) => {
  applyZoom(level)
  try {
    localStorage.setItem(STORAGE_KEY, String(level))
  } catch { /* ignore */ }
})

function setZoom(level: ZoomLevel) {
  zoom.value = level
}

export function useZoom() {
  return {
    zoom,
    zoomLevels: ZOOM_LEVELS,
    setZoom,
  }
}
