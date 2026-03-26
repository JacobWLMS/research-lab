<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useWebSocket } from '../../composables/useWebSocket'
import { useGpuStats } from '../../composables/useGpuStats'
import { useExperiments } from '../../composables/useExperiments'
import { useExperimentDetail } from '../../composables/useExperimentDetail'
import { useTheme } from '../../composables/useTheme'
import { useZoom, type ZoomLevel } from '../../composables/useZoom'
import { useToast } from '../../composables/useToast'
import { useToolbarContext } from '../../composables/useToolbarContext'
import { useNotifications } from '../../composables/useNotifications'
import StatusBadge from '../shared/StatusBadge.vue'
import NotificationPanel from '../shared/NotificationPanel.vue'
import TerminalPanel from '../shared/TerminalPanel.vue'
import ExperimentSelector from '../nav/ExperimentSelector.vue'
import PipelineNav from '../nav/PipelineNav.vue'
import ActivitySidebar from '../sidebar/ActivitySidebar.vue'
import DashboardView from '../dashboard/DashboardView.vue'
import StepView from '../dashboard/StepView.vue'

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

// Route-derived state
const experimentId = computed(() => {
  const id = route.params.id
  return typeof id === 'string' ? id : null
})

const stepName = computed(() => {
  const s = route.params.stepName
  return typeof s === 'string' ? s : null
})

// Wire up experiment detail composable
const {
  experiment,
  results,
  canvases,
  outputLines,
  liveMetrics,
  progress,
  loading,
  anyStepRunning,
  pipelineRunning,
  runStep,
  stopStep,
  updateStepCode,
  addStep,
  runPipeline,
  fetchExperiment,
  fetchResults,
} = useExperimentDetail(() => experimentId.value)

// Toolbar context
const overallStatus = computed(() => {
  if (!experiment.value) return 'pending'
  const s = experiment.value.steps.map((s) => s.status)
  if (s.some((x) => x === 'failed')) return 'failed'
  if (s.some((x) => x === 'running')) return 'running'
  if (s.length > 0 && s.every((x) => x === 'completed')) return 'completed'
  return 'pending'
})

const runAllDisabled = computed(() => anyStepRunning.value || pipelineRunning.value)

const toolbarCtx = useToolbarContext()

watch(
  [experiment, overallStatus, pipelineRunning, runAllDisabled],
  () => {
    if (experiment.value) {
      toolbarCtx.setContext({
        name: experiment.value.name,
        status: overallStatus.value,
        pipelineRunning: pipelineRunning.value,
        runAllDisabled: runAllDisabled.value,
        onRunPipeline: () => { if (!runAllDisabled.value) runPipeline() },
        onAddStep: openAddStep,
        onRefreshDetail: async () => {
          const id = experimentId.value
          if (id) {
            await fetchExperiment(id)
            await fetchResults(id)
          }
        },
      })
    } else {
      toolbarCtx.clearContext()
    }
  },
  { immediate: true },
)

// GPU VRAM
const gpuVramPct = computed(() => {
  if (!gpu.value || gpu.value.memory_total_gb <= 0) return 0
  return (gpu.value.memory_used_gb / gpu.value.memory_total_gb) * 100
})

const gpuVramColor = computed(() => {
  const pct = gpuVramPct.value
  if (pct >= 90) return 'var(--c-red)'
  if (pct >= 70) return 'var(--c-yellow)'
  return 'var(--c-green)'
})

// ---- Panel storage keys & helpers ----
const LS_LEFT_W = 'mc-left-width'
const LS_LEFT_C = 'mc-left-collapsed'
const LS_RIGHT_W = 'mc-right-width'
const LS_RIGHT_C = 'mc-right-collapsed'
const LS_TERM_H = 'mc-terminal-height'
const LS_TERM_C = 'mc-terminal-collapsed'

function lsGet(key: string, fallback: number, min: number, max: number): number {
  try { const v = Number(localStorage.getItem(key)); if (v >= min && v <= max) return v } catch {}
  return fallback
}
function lsBool(key: string, fallback: boolean): boolean {
  try { const v = localStorage.getItem(key); if (v !== null) return v === 'true' } catch {}
  return fallback
}

// Panel state
const leftWidth = ref(lsGet(LS_LEFT_W, 240, 180, 400))
const leftCollapsed = ref(lsBool(LS_LEFT_C, false))
const rightWidth = ref(lsGet(LS_RIGHT_W, 280, 200, 400))
const rightCollapsed = ref(lsBool(LS_RIGHT_C, false))
const terminalHeight = ref(lsGet(LS_TERM_H, 200, 100, 600))
const terminalOpen = ref(lsBool(LS_TERM_C, false))

// Persist
watch(leftWidth, (v) => { try { localStorage.setItem(LS_LEFT_W, String(v)) } catch {} })
watch(leftCollapsed, (v) => { try { localStorage.setItem(LS_LEFT_C, String(v)) } catch {} })
watch(rightWidth, (v) => { try { localStorage.setItem(LS_RIGHT_W, String(v)) } catch {} })
watch(rightCollapsed, (v) => { try { localStorage.setItem(LS_RIGHT_C, String(v)) } catch {} })
watch(terminalHeight, (v) => { try { localStorage.setItem(LS_TERM_H, String(v)) } catch {} })
watch(terminalOpen, (v) => { try { localStorage.setItem(LS_TERM_C, String(v)) } catch {} })

// Resize logic
const isResizing = ref<'left' | 'right' | 'terminal' | null>(null)
const resizeStart = ref({ x: 0, y: 0, size: 0 })

function startResize(panel: 'left' | 'right' | 'terminal', e: MouseEvent) {
  isResizing.value = panel
  resizeStart.value = {
    x: e.clientX,
    y: e.clientY,
    size: panel === 'left' ? leftWidth.value : panel === 'right' ? rightWidth.value : terminalHeight.value,
  }
  e.preventDefault()
}

function onMouseMove(e: MouseEvent) {
  if (!isResizing.value) return
  const p = isResizing.value
  if (p === 'left') {
    leftWidth.value = Math.max(180, Math.min(400, resizeStart.value.size + (e.clientX - resizeStart.value.x)))
  } else if (p === 'right') {
    rightWidth.value = Math.max(200, Math.min(400, resizeStart.value.size - (e.clientX - resizeStart.value.x)))
  } else if (p === 'terminal') {
    terminalHeight.value = Math.max(100, Math.min(600, resizeStart.value.size - (e.clientY - resizeStart.value.y)))
  }
}

function onMouseUp() {
  isResizing.value = null
}

// Other UI state
const { unreadCount } = useNotifications()
const refreshing = ref(false)
const showZoomDropdown = ref(false)
const showNotifications = ref(false)

// Add step
const showAddStep = ref(false)
const newStepName = ref('')
const addingStep = ref(false)
const stepNameInput = ref<HTMLInputElement | null>(null)

function openAddStep() {
  showAddStep.value = true
  newStepName.value = ''
  setTimeout(() => stepNameInput.value?.focus(), 50)
}

async function doAddStep() {
  const name = newStepName.value.trim()
  if (!name || addingStep.value) return
  addingStep.value = true
  await addStep(name)
  addingStep.value = false
  showAddStep.value = false
  newStepName.value = ''
}

async function doRefresh() {
  if (refreshing.value) return
  refreshing.value = true
  await fetchExperiments()
  triggerRefreshDetail()
  refreshing.value = false
}

function onZoomSelect(level: ZoomLevel) {
  setZoom(level)
  showZoomDropdown.value = false
}

function selectExperiment(id: string) {
  router.push({ name: 'experiment', params: { id } })
}

function navigateToStep(name: string) {
  if (!experimentId.value) return
  router.push({ name: 'step', params: { id: experimentId.value, stepName: name } })
}

function navigateToDashboard() {
  if (experimentId.value) {
    router.push({ name: 'experiment', params: { id: experimentId.value } })
  } else {
    router.push({ name: 'home' })
  }
}

function openAssetLibrary() {
  if (experimentId.value) {
    router.push({ name: 'assets', params: { id: experimentId.value } })
  }
}

// Keyboard shortcuts
function onKeydown(e: KeyboardEvent) {
  // Ctrl+`: Toggle terminal
  if (e.ctrlKey && e.key === '`') {
    e.preventDefault()
    terminalOpen.value = !terminalOpen.value
    return
  }
  // Ctrl+B: Toggle left nav
  if (e.ctrlKey && !e.shiftKey && e.key === 'b') {
    e.preventDefault()
    leftCollapsed.value = !leftCollapsed.value
    return
  }
  // Ctrl+Shift+B: Toggle right sidebar
  if (e.ctrlKey && e.shiftKey && e.key === 'B') {
    e.preventDefault()
    rightCollapsed.value = !rightCollapsed.value
    return
  }
  // Ctrl+Shift+Enter: Run pipeline
  if (e.ctrlKey && e.shiftKey && e.key === 'Enter') {
    e.preventDefault()
    if (!runAllDisabled.value) runPipeline()
    return
  }
  // Escape: go to dashboard
  if (e.key === 'Escape') {
    showZoomDropdown.value = false
    showNotifications.value = false
    if (stepName.value) {
      e.preventDefault()
      navigateToDashboard()
    }
    return
  }
}

function onDocClick(e: MouseEvent) {
  const target = e.target as HTMLElement
  if (!target.closest('.zoom-dropdown-area')) showZoomDropdown.value = false
  if (!target.closest('.notif-dropdown-area')) showNotifications.value = false
}

// WebSocket connection change
const unsubConnectionChange = onConnectionChange((state) => {
  if (state === 'disconnected') {
    toast.error('Connection lost -- reconnecting...')
  } else {
    toast.success('Connection restored')
    fetchExperiments()
  }
})

// Grid template columns
const gridCols = computed(() => {
  const l = leftCollapsed.value ? '0px' : `${leftWidth.value}px`
  const r = rightCollapsed.value ? '0px' : `${rightWidth.value}px`
  return `${l} auto 1fr auto ${r}`
})

// Grid template rows
const gridRows = computed(() => {
  const t = terminalOpen.value ? `auto ${terminalHeight.value}px` : ''
  return `auto 1fr ${t}`
})

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
  toolbarCtx.clearContext()
})
</script>

<template>
  <div
    class="mc"
    :class="{
      'mc--resizing': isResizing !== null,
      'mc--left-collapsed': leftCollapsed,
      'mc--right-collapsed': rightCollapsed,
    }"
    :style="{
      'grid-template-columns': gridCols,
      'grid-template-rows': gridRows,
    }"
  >
    <!-- ====== TOOLBAR (row 1, spans all columns) ====== -->
    <header class="mc__toolbar">
      <!-- Left: hamburger + logo + experiment selector -->
      <div class="mc__toolbar-left">
        <button
          class="mc__icon-btn"
          title="Toggle left nav (Ctrl+B)"
          @click="leftCollapsed = !leftCollapsed"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M3 6h18M3 12h18M3 18h18" stroke-linecap="round"/>
          </svg>
        </button>
        <div class="mc__logo">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="color: var(--c-aqua)">
            <polygon points="12 2 22 8.5 22 15.5 12 22 2 15.5 2 8.5 12 2"/>
          </svg>
          <span class="mc__logo-text">research-lab</span>
        </div>
        <ExperimentSelector
          :selected-id="experimentId ?? undefined"
          @select="selectExperiment"
        />
      </div>

      <!-- Center: GPU stats -->
      <div class="mc__toolbar-center">
        <template v-if="gpu">
          <span class="mc__gpu-dot" :style="{ background: gpuVramColor }" :title="`VRAM ${Math.round(gpuVramPct)}%`" />
          <span class="mc__gpu-bar-wrap">
            <span class="mc__gpu-bar-fill" :style="{ width: gpu.utilization_pct + '%' }" />
          </span>
          <span class="mc__gpu-text">
            <span class="mc__gpu-val">{{ gpu.utilization_pct }}%</span>
            <span class="mc__gpu-sep">|</span>
            <span class="mc__gpu-val" :style="{ color: gpuVramColor }">{{ gpu.memory_used_gb.toFixed(1) }}/{{ gpu.memory_total_gb.toFixed(0) }}GB</span>
            <span class="mc__gpu-sep">|</span>
            <span class="mc__gpu-val">{{ gpu.temperature_c }}&deg;C</span>
          </span>
        </template>
      </div>

      <!-- Right: actions + controls -->
      <div class="mc__toolbar-right">
        <template v-if="experimentName">
          <button
            class="mc__action-btn mc__action-btn--primary"
            :class="{ 'mc__action-btn--disabled': toolbarRunAllDisabled }"
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
          <button class="mc__action-btn" @click="openAddStep" title="Add step">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M12 5v14m-7-7h14" stroke-linecap="round"/>
            </svg>
            Add Step
          </button>
          <span class="mc__toolbar-divider" />
        </template>

        <!-- Theme toggle -->
        <button class="mc__icon-btn" :title="theme === 'dark' ? 'Switch to light' : 'Switch to dark'" @click="toggleTheme">
          <svg v-if="theme === 'dark'" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="5"/><path d="M12 1v2m0 18v2m-9-11h2m18 0h2m-3.6-6.4l-1.4 1.4M6.3 17.7l-1.4 1.4m0-12.8l1.4 1.4m11.4 11.4l1.4 1.4" stroke-linecap="round"/>
          </svg>
          <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 12.79A9 9 0 1111.21 3a7 7 0 109.79 9.79z" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </button>

        <!-- Zoom -->
        <div class="zoom-dropdown-area" style="position: relative">
          <button class="mc__zoom-btn" @click.stop="showZoomDropdown = !showZoomDropdown">
            {{ zoom }}%
            <svg width="8" height="8" viewBox="0 0 24 24" fill="currentColor"><path d="M7 10l5 5 5-5z"/></svg>
          </button>
          <div v-if="showZoomDropdown" class="mc__zoom-menu animate-slide-up">
            <button
              v-for="level in zoomLevels" :key="level"
              class="mc__zoom-option"
              :class="{ 'mc__zoom-option--active': level === zoom }"
              @click="onZoomSelect(level)"
            >{{ level }}%</button>
          </div>
        </div>

        <!-- Refresh -->
        <button class="mc__icon-btn" :class="{ 'mc__icon-btn--spinning': refreshing }" title="Refresh (Ctrl+R)" @click="doRefresh">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M23 4v6h-6" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M20.49 15a9 9 0 11-2.12-9.36L23 10" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </button>

        <!-- Connection dot -->
        <span
          class="mc__conn-dot"
          :style="{ background: connected ? 'var(--c-green)' : 'var(--c-red)' }"
          :title="connected ? 'Connected' : 'Disconnected'"
        />

        <!-- Notification bell -->
        <div class="notif-dropdown-area" style="position: relative">
          <button class="mc__icon-btn mc__notif-btn" title="Notifications" @click.stop="showNotifications = !showNotifications">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M18 8A6 6 0 006 8c0 7-3 9-3 9h18s-3-2-3-9" stroke-linecap="round" stroke-linejoin="round"/>
              <path d="M13.73 21a2 2 0 01-3.46 0" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
            <span v-if="unreadCount > 0" class="mc__notif-badge">{{ unreadCount > 9 ? '9+' : unreadCount }}</span>
          </button>
          <NotificationPanel v-if="showNotifications" />
        </div>

        <!-- Toggle right sidebar -->
        <button class="mc__icon-btn" title="Toggle sidebar (Ctrl+Shift+B)" @click="rightCollapsed = !rightCollapsed">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <rect x="3" y="3" width="18" height="18" rx="2"/>
            <path d="M15 3v18"/>
          </svg>
        </button>
      </div>
    </header>

    <!-- ====== LEFT NAV ====== -->
    <aside v-if="!leftCollapsed" class="mc__left-nav">
      <!-- Add Step inline form -->
      <div v-if="showAddStep" class="mc__add-step animate-slide-up">
        <input
          ref="stepNameInput"
          v-model="newStepName"
          class="mc__add-step-input"
          placeholder="Step name..."
          @keydown.enter="doAddStep"
          @keydown.escape="showAddStep = false"
        />
        <button class="mc__add-step-submit" :disabled="!newStepName.trim() || addingStep" @click="doAddStep">
          {{ addingStep ? '...' : 'Add' }}
        </button>
        <button class="mc__add-step-cancel" @click="showAddStep = false">
          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6L6 18M6 6l12 12" stroke-linecap="round"/></svg>
        </button>
      </div>
      <PipelineNav
        v-if="experiment"
        :steps="experiment.steps"
        :results="results"
        :canvases="canvases"
        :active-step="stepName ?? undefined"
        @click-step="navigateToStep"
        @click-dashboard="navigateToDashboard"
        @open-assets="openAssetLibrary"
      />
      <div v-else-if="!experimentId" class="mc__left-empty">
        <span class="mc__left-empty-text">Select an experiment</span>
      </div>
      <div v-else-if="loading" class="mc__left-empty">
        <svg class="animate-spin" width="14" height="14" viewBox="0 0 24 24" fill="none" style="color: var(--c-fg-dim)">
          <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="2" opacity="0.25"/>
          <path d="M4 12a8 8 0 018-8" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
        </svg>
      </div>
    </aside>

    <!-- Left resize handle -->
    <div
      v-if="!leftCollapsed"
      class="mc__resize-handle mc__resize-handle--v"
      :class="{ 'mc__resize-handle--active': isResizing === 'left' }"
      @mousedown="startResize('left', $event)"
    />

    <!-- ====== MAIN STAGE ====== -->
    <main class="mc__main">
      <!-- No experiment: empty state -->
      <div v-if="!experimentId" class="mc__main-empty">
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="color: var(--c-fg-dim)">
          <polygon points="12 2 22 8.5 22 15.5 12 22 2 15.5 2 8.5 12 2"/>
        </svg>
        <span style="color: var(--c-fg-muted)">Select an experiment to begin</span>
      </div>

      <!-- Loading -->
      <div v-else-if="loading && !experiment" class="mc__main-empty">
        <svg class="animate-spin" width="16" height="16" viewBox="0 0 24 24" fill="none" style="color: var(--c-fg-dim)">
          <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="2" opacity="0.25"/>
          <path d="M4 12a8 8 0 018-8" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
        </svg>
        <span>Loading...</span>
      </div>

      <!-- Step view -->
      <StepView
        v-else-if="experiment && stepName"
        :key="`step-${experimentId}-${stepName}`"
        :experiment-id="experimentId!"
        :step="experiment.steps.find(s => s.name === stepName) ?? null"
        :result="results[stepName] ?? undefined"
        :canvases="canvases[stepName] ?? []"
        :output-lines="outputLines[stepName] ?? []"
        :live-metrics="liveMetrics[stepName] ?? {}"
        :progress="progress[stepName]"
        @run="runStep(stepName!)"
        @stop="stopStep(stepName!)"
        @update-code="(code: string) => updateStepCode(stepName!, code)"
        @navigate-dashboard="navigateToDashboard"
      />

      <!-- Dashboard view -->
      <DashboardView
        v-else-if="experiment"
        :key="`dash-${experimentId}`"
        :experiment-id="experimentId!"
        :experiment="experiment"
        :results="results"
        :canvases="canvases"
        :output-lines="outputLines"
        :live-metrics="liveMetrics"
        :progress="progress"
        @click-step="navigateToStep"
      />
    </main>

    <!-- Right resize handle -->
    <div
      v-if="!rightCollapsed"
      class="mc__resize-handle mc__resize-handle--v"
      :class="{ 'mc__resize-handle--active': isResizing === 'right' }"
      @mousedown="startResize('right', $event)"
    />

    <!-- ====== RIGHT SIDEBAR ====== -->
    <aside v-if="!rightCollapsed" class="mc__right-sidebar">
      <ActivitySidebar
        :live-metrics="experimentId ? (liveMetrics ?? {}) : {}"
        :experiment-id="experimentId"
      />
    </aside>

    <!-- ====== TERMINAL RESIZE HANDLE ====== -->
    <div
      v-if="terminalOpen"
      class="mc__resize-handle mc__resize-handle--h"
      :class="{ 'mc__resize-handle--active': isResizing === 'terminal' }"
      @mousedown="startResize('terminal', $event)"
    />

    <!-- ====== TERMINAL ====== -->
    <div v-if="terminalOpen" class="mc__terminal" :style="{ height: terminalHeight + 'px' }">
      <TerminalPanel />
    </div>
  </div>
</template>

<style scoped>
.mc {
  display: grid;
  height: 100vh;
  overflow: hidden;
}

.mc--resizing {
  user-select: none;
}

/* ---- Toolbar (row 1, spans all cols) ---- */
.mc__toolbar {
  grid-column: 1 / -1;
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 2.5rem;
  padding: 0 0.5rem;
  background: var(--c-surface);
  border-bottom: var(--mc-panel-border);
  flex-shrink: 0;
  gap: 0.5rem;
  user-select: none;
  z-index: 10;
}

.mc__toolbar-left {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  flex-shrink: 1;
  min-width: 0;
  overflow: hidden;
}

.mc__toolbar-center {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  font-size: var(--mc-label-size);
  color: var(--c-fg-muted);
  flex-shrink: 1;
  overflow: hidden;
}

.mc__toolbar-right {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  flex-shrink: 0;
}

.mc__logo {
  display: flex;
  align-items: center;
  gap: 0.25rem;
}

.mc__logo-text {
  font-size: 0.8125rem;
  font-weight: 600;
  letter-spacing: -0.01em;
  color: var(--c-aqua);
}

/* Icon button */
.mc__icon-btn {
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

.mc__icon-btn:hover { background: var(--c-surface-hover); color: var(--c-fg); }
.mc__icon-btn--spinning svg { animation: spin 0.8s linear infinite; }

/* Action buttons */
.mc__action-btn {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.1875rem 0.5rem;
  font-size: var(--mc-label-size);
  font-weight: 500;
  color: var(--c-fg-muted);
  background: var(--c-bg1);
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: background 0.12s, color 0.12s;
  white-space: nowrap;
  height: 1.5rem;
}

.mc__action-btn:hover { background: var(--c-surface-hover); color: var(--c-fg); }
.mc__action-btn--primary { background: var(--c-aqua); color: var(--c-bg-hard); }
.mc__action-btn--primary:hover { filter: brightness(1.1); }
.mc__action-btn--disabled { opacity: 0.5; cursor: not-allowed; }
.mc__action-btn--disabled:hover { filter: none; }

.mc__toolbar-divider {
  display: block;
  width: 1px;
  height: 1rem;
  background: var(--c-border);
  margin: 0 0.125rem;
  flex-shrink: 0;
}

/* GPU stats */
.mc__gpu-dot {
  width: 0.5rem;
  height: 0.5rem;
  border-radius: 50%;
  flex-shrink: 0;
  transition: background 0.3s;
}

.mc__gpu-bar-wrap {
  width: 3rem;
  height: 0.375rem;
  background: var(--c-bg2);
  border-radius: 2px;
  overflow: hidden;
  flex-shrink: 0;
}

.mc__gpu-bar-fill {
  display: block;
  height: 100%;
  background: var(--c-aqua);
  transition: width 0.3s;
  border-radius: 2px;
}

.mc__gpu-text {
  display: flex;
  align-items: center;
  gap: 0.25rem;
}

.mc__gpu-val {
  font-family: var(--font-mono);
  font-size: var(--mc-label-size);
  color: var(--c-fg);
  white-space: nowrap;
}

.mc__gpu-sep { color: var(--c-bg3); }

/* Zoom */
.mc__zoom-btn {
  display: flex;
  align-items: center;
  gap: 0.125rem;
  height: 1.75rem;
  padding: 0 0.375rem;
  font-size: var(--mc-label-size);
  font-family: var(--font-mono);
  color: var(--c-fg-muted);
  background: transparent;
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
}

.mc__zoom-btn:hover { background: var(--c-surface-hover); color: var(--c-fg); }

.mc__zoom-menu {
  position: absolute;
  top: 100%;
  right: 0;
  margin-top: 0.25rem;
  background: var(--c-bg);
  border: 1px solid var(--c-border);
  border-radius: var(--radius-md);
  box-shadow: 0 4px 12px rgba(0,0,0,0.25);
  z-index: 100;
  overflow: hidden;
  min-width: 4rem;
}

.mc__zoom-option {
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
}

.mc__zoom-option:hover { background: var(--c-surface-hover); color: var(--c-fg); }
.mc__zoom-option--active { color: var(--c-aqua); font-weight: 600; }

/* Connection dot */
.mc__conn-dot {
  width: 0.5rem;
  height: 0.5rem;
  border-radius: 50%;
  flex-shrink: 0;
  transition: background 0.2s;
}

/* Notification badge */
.mc__notif-btn { position: relative; }
.mc__notif-badge {
  position: absolute;
  top: 0.0625rem;
  right: 0.0625rem;
  min-width: 0.875rem;
  height: 0.875rem;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 0.1875rem;
  font-size: 0.5625rem;
  font-weight: 700;
  font-family: var(--font-mono);
  color: var(--c-bg-hard);
  background: var(--c-red);
  border-radius: 0.4375rem;
  pointer-events: none;
  line-height: 1;
}

/* ---- Left Nav ---- */
.mc__left-nav {
  overflow-y: auto;
  overflow-x: hidden;
  background: var(--c-bg-hard);
  border-right: var(--mc-panel-border);
}

.mc__left-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  font-size: var(--mc-label-size);
  color: var(--c-fg-dim);
}

.mc__left-empty-text {
  padding: 1rem;
  text-align: center;
}

/* Add step inline form */
.mc__add-step {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.375rem 0.5rem;
  border-bottom: 1px solid var(--c-border-subtle);
  background: var(--c-bg1);
}

.mc__add-step-input {
  flex: 1;
  font-size: var(--mc-label-size);
  padding: 0.1875rem 0.375rem;
  background: var(--c-bg-hard);
  color: var(--c-fg);
  border: 1px solid var(--c-border);
  border-radius: var(--radius-sm);
  outline: none;
  min-width: 0;
}

.mc__add-step-input:focus { border-color: var(--c-aqua); }

.mc__add-step-submit {
  font-size: var(--mc-label-size);
  padding: 0.1875rem 0.375rem;
  background: var(--c-aqua);
  color: var(--c-bg-hard);
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
  flex-shrink: 0;
}

.mc__add-step-submit:disabled { opacity: 0.4; cursor: not-allowed; }

.mc__add-step-cancel {
  display: flex;
  align-items: center;
  padding: 0.125rem;
  color: var(--c-fg-dim);
  background: transparent;
  border: none;
  cursor: pointer;
}

/* ---- Main Stage ---- */
.mc__main {
  overflow: hidden;
  background: var(--c-bg-hard);
  min-width: 20rem;
}

.mc__main-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  gap: 0.75rem;
  font-size: 0.8125rem;
  color: var(--c-fg-dim);
}

/* ---- Right Sidebar ---- */
.mc__right-sidebar {
  overflow-y: auto;
  overflow-x: hidden;
  background: var(--c-bg-hard);
  border-left: var(--mc-panel-border);
}

/* ---- Resize handles ---- */
.mc__resize-handle {
  background: transparent;
  transition: background 0.12s;
  position: relative;
  z-index: 5;
}

.mc__resize-handle--v {
  width: 3px;
  cursor: col-resize;
}

.mc__resize-handle--v::after {
  content: '';
  position: absolute;
  left: -2px;
  right: -2px;
  top: 0;
  bottom: 0;
}

.mc__resize-handle--h {
  grid-column: 1 / -1;
  height: 3px;
  cursor: row-resize;
}

.mc__resize-handle--h::after {
  content: '';
  position: absolute;
  top: -2px;
  bottom: -2px;
  left: 0;
  right: 0;
}

.mc__resize-handle:hover,
.mc__resize-handle--active {
  background: var(--c-aqua);
}

/* ---- Terminal ---- */
.mc__terminal {
  grid-column: 1 / -1;
  border-top: var(--mc-panel-border);
  overflow: hidden;
}

/* ---- Responsive ---- */
@media (max-width: 1200px) {
  .mc__gpu-text { display: none; }
}

@media (max-width: 900px) {
  .mc__gpu-text { display: none; }
  .mc__gpu-bar-wrap { display: none; }
  .zoom-dropdown-area { display: none; }
}
</style>
