<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useWebSocket } from '../../composables/useWebSocket'
import { useGpuStats } from '../../composables/useGpuStats'
import { useExperiments } from '../../composables/useExperiments'
import { useTheme } from '../../composables/useTheme'
import { useZoom, type ZoomLevel } from '../../composables/useZoom'
import { useToast } from '../../composables/useToast'
import { useToolbarContext } from '../../composables/useToolbarContext'
import ExperimentList from '../experiment/ExperimentList.vue'
import StatusBadge from '../shared/StatusBadge.vue'

const router = useRouter()
const route = useRoute()
const { connected, connect, onConnectionChange } = useWebSocket()
const { gpu } = useGpuStats()
const { fetchExperiments } = useExperiments()
const { theme, toggleTheme } = useTheme()
const { zoom, zoomLevels, setZoom } = useZoom()
const toast = useToast()
const {
  experimentName,
  experimentStatus,
  pipelineRunning: toolbarPipelineRunning,
  runAllDisabled: toolbarRunAllDisabled,
  triggerRunPipeline,
  triggerAddStep,
  triggerRefreshDetail,
} = useToolbarContext()

// GPU VRAM utilization color indicator
const gpuVramPct = computed(() => {
  if (!gpu.value) return 0
  if (gpu.value.memory_total_gb <= 0) return 0
  return (gpu.value.memory_used_gb / gpu.value.memory_total_gb) * 100
})

const gpuVramColor = computed(() => {
  const pct = gpuVramPct.value
  if (pct >= 90) return 'var(--c-red)'
  if (pct >= 70) return 'var(--c-yellow)'
  return 'var(--c-green)'
})


// Panel state
const PANEL_STORAGE_KEY = 'research-lab-panel-width'
const PANEL_COLLAPSED_KEY = 'research-lab-panel-collapsed'

function getStoredPanelWidth(): number {
  try {
    const v = Number(localStorage.getItem(PANEL_STORAGE_KEY))
    if (v >= 200 && v <= 450) return v
  } catch { /* ignore */ }
  return 260
}

function getStoredPanelCollapsed(): boolean {
  try {
    return localStorage.getItem(PANEL_COLLAPSED_KEY) === 'true'
  } catch { /* ignore */ }
  return false
}

const panelWidth = ref(getStoredPanelWidth())
const panelCollapsed = ref(getStoredPanelCollapsed())
const isResizing = ref(false)
const MIN_W = 200
const MAX_W = 450

const refreshing = ref(false)
const showZoomDropdown = ref(false)

// Persist panel state
watch(panelWidth, (w) => {
  try { localStorage.setItem(PANEL_STORAGE_KEY, String(w)) } catch { /* ignore */ }
})
watch(panelCollapsed, (c) => {
  try { localStorage.setItem(PANEL_COLLAPSED_KEY, String(c)) } catch { /* ignore */ }
})

function onMouseDown(e: MouseEvent) {
  isResizing.value = true
  e.preventDefault()
}

function onMouseMove(e: MouseEvent) {
  if (!isResizing.value) return
  panelWidth.value = Math.min(Math.max(e.clientX, MIN_W), MAX_W)
}

function onMouseUp() {
  isResizing.value = false
}

function selectExperiment(id: string) {
  router.push({ name: 'experiment', params: { id } })
}

async function doRefresh() {
  if (refreshing.value) return
  refreshing.value = true
  await fetchExperiments()
  triggerRefreshDetail()
  refreshing.value = false
}

function togglePanel() {
  panelCollapsed.value = !panelCollapsed.value
}

function onZoomSelect(level: ZoomLevel) {
  setZoom(level)
  showZoomDropdown.value = false
}

// Keyboard shortcuts
function onKeydown(e: KeyboardEvent) {
  // Ctrl+R or F5: Refresh
  if ((e.ctrlKey && e.key === 'r') || e.key === 'F5') {
    e.preventDefault()
    doRefresh()
    return
  }
  // Ctrl+`: Toggle panel
  if (e.ctrlKey && e.key === '`') {
    e.preventDefault()
    togglePanel()
    return
  }
  // Escape: Close zoom dropdown
  if (e.key === 'Escape') {
    showZoomDropdown.value = false
  }
}

// Close zoom dropdown on outside click
function onDocClick(e: MouseEvent) {
  const target = e.target as HTMLElement
  if (!target.closest('.zoom-dropdown-area')) {
    showZoomDropdown.value = false
  }
}

// WebSocket connection state notifications
const unsubConnectionChange = onConnectionChange((state) => {
  if (state === 'disconnected') {
    toast.error('Connection lost -- reconnecting...')
  } else {
    toast.success('Connection restored')
    // Auto-refresh on reconnect
    fetchExperiments()
  }
})

// Computed: effective panel width
const effectivePanelWidth = computed(() =>
  panelCollapsed.value ? 0 : panelWidth.value
)

onMounted(() => {
  connect()
  fetchExperiments()
  document.addEventListener('mousemove', onMouseMove)
  document.addEventListener('mouseup', onMouseUp)
  document.addEventListener('keydown', onKeydown)
  document.addEventListener('click', onDocClick)
})

onUnmounted(() => {
  document.removeEventListener('mousemove', onMouseMove)
  document.removeEventListener('mouseup', onMouseUp)
  document.removeEventListener('keydown', onKeydown)
  document.removeEventListener('click', onDocClick)
  unsubConnectionChange()
})
</script>

<template>
  <div class="app-shell">
    <!-- ====== Top Toolbar ====== -->
    <header class="app-shell__toolbar">
      <!-- Left group: collapse toggle + logo + experiment breadcrumb -->
      <div class="app-shell__toolbar-left">
        <button
          class="app-shell__icon-btn"
          title="Toggle sidebar (Ctrl+`)"
          @click="togglePanel"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M3 6h18M3 12h18M3 18h18" stroke-linecap="round"/>
          </svg>
        </button>
        <div class="app-shell__logo">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="color: var(--c-aqua)">
            <polygon points="12 2 22 8.5 22 15.5 12 22 2 15.5 2 8.5 12 2"/>
          </svg>
          <span class="app-shell__title">research-lab</span>
        </div>
        <!-- Experiment breadcrumb (shown when an experiment is active) -->
        <template v-if="experimentName">
          <span class="app-shell__breadcrumb-sep">/</span>
          <span class="app-shell__breadcrumb-name">{{ experimentName }}</span>
          <StatusBadge :status="experimentStatus" :show-label="false" />
        </template>
      </div>

      <!-- Center group: GPU stats -->
      <div class="app-shell__toolbar-center">
        <template v-if="gpu">
          <span
            class="app-shell__gpu-dot"
            :style="{ background: gpuVramColor }"
            :title="`VRAM ${Math.round(gpuVramPct)}%`"
          />
          <span class="app-shell__gpu-text">
            <span class="app-shell__gpu-val">GPU {{ gpu.utilization_pct }}%</span>
            <span class="app-shell__gpu-sep">|</span>
            <span class="app-shell__gpu-val" :style="{ color: gpuVramColor }">{{ gpu.memory_used_gb.toFixed(1) }}/{{ gpu.memory_total_gb.toFixed(0) }}GB</span>
            <span class="app-shell__gpu-sep">|</span>
            <span class="app-shell__gpu-val">{{ gpu.temperature_c }}&deg;C</span>
          </span>
        </template>
      </div>

      <!-- Right group: experiment actions + global controls + status -->
      <div class="app-shell__toolbar-right">
        <!-- Experiment actions (shown when an experiment is active) -->
        <template v-if="experimentName">
          <!-- Run Pipeline -->
          <button
            class="app-shell__action-btn app-shell__action-btn--primary"
            :class="{ 'app-shell__action-btn--disabled': toolbarRunAllDisabled }"
            :disabled="toolbarRunAllDisabled"
            title="Run full pipeline (Ctrl+Shift+Enter)"
            @click="triggerRunPipeline"
          >
            <svg v-if="toolbarPipelineRunning" class="animate-spin" width="12" height="12" viewBox="0 0 24 24" fill="none">
              <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="2.5" opacity="0.3"/>
              <path d="M4 12a8 8 0 018-8" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"/>
            </svg>
            <svg v-else width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>
            {{ toolbarPipelineRunning ? 'Running...' : 'Run Pipeline' }}
          </button>

          <!-- Add Step -->
          <button class="app-shell__action-btn" @click="triggerAddStep">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M12 5v14m-7-7h14" stroke-linecap="round"/>
            </svg>
            Add Step
          </button>

          <span class="app-shell__toolbar-divider" />
        </template>

        <!-- Refresh -->
        <button
          class="app-shell__icon-btn"
          :class="{ 'app-shell__icon-btn--spinning': refreshing }"
          title="Refresh all data (Ctrl+R)"
          @click="doRefresh"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M23 4v6h-6" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M20.49 15a9 9 0 11-2.12-9.36L23 10" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </button>

        <!-- Theme toggle -->
        <button
          class="app-shell__icon-btn"
          :title="theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'"
          @click="toggleTheme"
        >
          <!-- Sun (shown in dark mode) -->
          <svg v-if="theme === 'dark'" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="5"/>
            <path d="M12 1v2m0 18v2m-9-11h2m18 0h2m-3.6-6.4l-1.4 1.4M6.3 17.7l-1.4 1.4m0-12.8l1.4 1.4m11.4 11.4l1.4 1.4" stroke-linecap="round"/>
          </svg>
          <!-- Moon (shown in light mode) -->
          <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 12.79A9 9 0 1111.21 3a7 7 0 109.79 9.79z" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </button>

        <!-- Zoom dropdown -->
        <div class="zoom-dropdown-area" style="position: relative">
          <button
            class="app-shell__zoom-btn"
            title="Zoom level"
            @click.stop="showZoomDropdown = !showZoomDropdown"
          >
            {{ zoom }}%
            <svg width="8" height="8" viewBox="0 0 24 24" fill="currentColor">
              <path d="M7 10l5 5 5-5z"/>
            </svg>
          </button>
          <div v-if="showZoomDropdown" class="app-shell__zoom-menu animate-slide-up">
            <button
              v-for="level in zoomLevels"
              :key="level"
              class="app-shell__zoom-option"
              :class="{ 'app-shell__zoom-option--active': level === zoom }"
              @click="onZoomSelect(level)"
            >{{ level }}%</button>
          </div>
        </div>

        <!-- Connection indicator -->
        <div class="app-shell__conn-status" :title="connected ? 'WebSocket connected' : 'WebSocket disconnected'">
          <span
            class="app-shell__conn-dot"
            :style="{ background: connected ? 'var(--c-green)' : 'var(--c-red)' }"
          />
          <span class="app-shell__conn-label">
            {{ connected ? 'Connected' : 'Disconnected' }}
          </span>
        </div>
      </div>
    </header>

    <!-- ====== Main Body ====== -->
    <div class="app-shell__body" :class="{ 'app-shell__body--resizing': isResizing }">
      <!-- Left panel (collapsible) -->
      <aside
        class="app-shell__sidebar"
        :style="{ width: effectivePanelWidth + 'px' }"
      >
        <ExperimentList
          v-if="!panelCollapsed"
          :selected-id="typeof route.params.id === 'string' ? route.params.id : undefined"
          @select="selectExperiment"
        />
      </aside>

      <!-- Resize handle -->
      <div
        v-if="!panelCollapsed"
        class="app-shell__resize-handle"
        :class="{ 'app-shell__resize-handle--active': isResizing }"
        @mousedown="onMouseDown"
      />

      <!-- Main content -->
      <main class="app-shell__main">
        <slot />
      </main>
    </div>
  </div>
</template>

<style scoped>
.app-shell {
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;
}

/* ---- Toolbar ---- */
.app-shell__toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 2.5rem; /* 40px at 100% zoom */
  padding: 0 0.75rem;
  background: var(--c-surface);
  border-bottom: 1px solid var(--c-border);
  flex-shrink: 0;
  gap: 0.75rem;
  user-select: none;
}

.app-shell__toolbar-left {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-shrink: 1;
  min-width: 0;
  overflow: hidden;
}

.app-shell__toolbar-center {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  font-size: 0.75rem;
  color: var(--c-fg-muted);
  flex-shrink: 1;
  overflow: hidden;
}

.app-shell__toolbar-right {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  flex-shrink: 0;
}

.app-shell__logo {
  display: flex;
  align-items: center;
  gap: 0.375rem;
}

.app-shell__title {
  font-size: 0.8125rem;
  font-weight: 600;
  letter-spacing: -0.01em;
  color: var(--c-aqua);
}

/* Experiment breadcrumb in toolbar */
.app-shell__breadcrumb-sep {
  color: var(--c-fg-dim);
  font-size: 0.75rem;
  margin: 0 0.125rem;
  user-select: none;
}

.app-shell__breadcrumb-name {
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--c-fg);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 14rem;
}

/* Toolbar action buttons (Run Pipeline, Add Step) */
.app-shell__action-btn {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.1875rem 0.625rem;
  font-size: 0.6875rem;
  font-weight: 500;
  color: var(--c-fg-muted);
  background: var(--c-bg1);
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: background 0.12s, color 0.12s;
  white-space: nowrap;
  height: 1.625rem;
}

.app-shell__action-btn:hover {
  background: var(--c-surface-hover);
  color: var(--c-fg);
}

.app-shell__action-btn--primary {
  background: var(--c-aqua);
  color: var(--c-bg-hard);
}

.app-shell__action-btn--primary:hover {
  filter: brightness(1.1);
}

.app-shell__action-btn--disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.app-shell__action-btn--disabled:hover {
  filter: none;
}

/* Divider between experiment actions and global controls */
.app-shell__toolbar-divider {
  display: block;
  width: 1px;
  height: 1rem;
  background: var(--c-border);
  margin: 0 0.125rem;
  flex-shrink: 0;
}

/* Icon button */
.app-shell__icon-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 1.75rem;
  height: 1.75rem;
  color: var(--c-fg-muted);
  background: transparent;
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: background 0.12s, color 0.12s;
}

.app-shell__icon-btn:hover {
  background: var(--c-surface-hover);
  color: var(--c-fg);
}

.app-shell__icon-btn--spinning svg {
  animation: spin 0.8s linear infinite;
}

/* GPU stats */
.app-shell__gpu-dot {
  width: 0.5rem;
  height: 0.5rem;
  border-radius: 50%;
  flex-shrink: 0;
  transition: background 0.3s;
}

.app-shell__gpu-text {
  display: flex;
  align-items: center;
  gap: 0.375rem;
}

.app-shell__gpu-val {
  font-family: var(--font-mono);
  color: var(--c-fg);
  white-space: nowrap;
}

.app-shell__gpu-sep {
  color: var(--c-bg3);
}

/* Zoom button */
.app-shell__zoom-btn {
  display: flex;
  align-items: center;
  gap: 0.125rem;
  height: 1.75rem;
  padding: 0 0.375rem;
  font-size: 0.6875rem;
  font-family: var(--font-mono);
  color: var(--c-fg-muted);
  background: transparent;
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: background 0.12s, color 0.12s;
}

.app-shell__zoom-btn:hover {
  background: var(--c-surface-hover);
  color: var(--c-fg);
}

.app-shell__zoom-menu {
  position: absolute;
  top: 100%;
  right: 0;
  margin-top: 0.25rem;
  background: var(--c-bg);
  border: 1px solid var(--c-border);
  border-radius: var(--radius-md);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25);
  z-index: 100;
  overflow: hidden;
  min-width: 4rem;
}

.app-shell__zoom-option {
  display: block;
  width: 100%;
  padding: 0.375rem 0.75rem;
  font-size: 0.75rem;
  font-family: var(--font-mono);
  text-align: right;
  color: var(--c-fg-muted);
  background: transparent;
  border: none;
  cursor: pointer;
  transition: background 0.08s, color 0.08s;
}

.app-shell__zoom-option:hover {
  background: var(--c-surface-hover);
  color: var(--c-fg);
}

.app-shell__zoom-option--active {
  color: var(--c-aqua);
  font-weight: 600;
}

/* Connection status */
.app-shell__conn-status {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  padding-left: 0.5rem;
  border-left: 1px solid var(--c-border);
  height: 1.25rem;
}

.app-shell__conn-dot {
  width: 0.5rem;
  height: 0.5rem;
  border-radius: 50%;
  flex-shrink: 0;
  transition: background 0.2s;
}

.app-shell__conn-label {
  font-size: 0.6875rem;
  color: var(--c-fg-muted);
  white-space: nowrap;
}

/* ---- Body / Panels ---- */
.app-shell__body {
  display: flex;
  flex: 1;
  overflow: hidden;
}

.app-shell__body--resizing {
  cursor: col-resize;
  user-select: none;
}

.app-shell__sidebar {
  flex-shrink: 0;
  overflow-y: auto;
  overflow-x: hidden;
  background: var(--c-bg-hard);
  border-right: 1px solid var(--c-border);
  transition: width 0.15s cubic-bezier(0.15, 0.9, 0.25, 1);
}

.app-shell__resize-handle {
  width: 3px;
  flex-shrink: 0;
  cursor: col-resize;
  background: transparent;
  transition: background 0.12s;
  position: relative;
}

.app-shell__resize-handle::after {
  content: '';
  position: absolute;
  left: -2px;
  right: -2px;
  top: 0;
  bottom: 0;
}

.app-shell__resize-handle:hover,
.app-shell__resize-handle--active {
  background: var(--c-aqua);
}

.app-shell__main {
  flex: 1;
  overflow: hidden;
  background: var(--c-bg-hard);
  min-width: 25rem; /* 400px */
}

/* ---- Responsive: hide GPU text on narrower screens, just show dot ---- */
@media (max-width: 1200px) {
  .app-shell__gpu-text {
    display: none;
  }
}

/* ---- Responsive: collapse zoom + connection label on narrow screens ---- */
@media (max-width: 900px) {
  .app-shell__gpu-text {
    display: none;
  }

  .zoom-dropdown-area {
    display: none;
  }

  .app-shell__conn-label {
    display: none;
  }

  .app-shell__breadcrumb-name {
    max-width: 8rem;
  }

  .app-shell__action-btn {
    padding: 0.1875rem 0.375rem;
    font-size: 0.625rem;
  }
}
</style>
