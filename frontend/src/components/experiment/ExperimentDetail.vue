<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useExperimentDetail } from '../../composables/useExperimentDetail'
import { useToolbarContext } from '../../composables/useToolbarContext'
import type { AssetsResponse } from '../../types'
import PipelineBar from './PipelineBar.vue'
import StepCanvas from './StepCanvas.vue'
import TerminalPanel from '../shared/TerminalPanel.vue'

const props = defineProps<{
  id?: string
}>()

const route = useRoute()
const appRouter = useRouter()
const experimentId = computed(() => props.id ?? (route.params.id as string | undefined) ?? null)

// Asset count for the "Assets" button badge
const assetCount = ref(0)

async function fetchAssetCount(id: string) {
  try {
    const res = await fetch(`/api/experiments/${id}/assets`)
    if (!res.ok) return
    const data: AssetsResponse = await res.json()
    assetCount.value = data.images.length + data.artifacts.length
  } catch {
    // non-fatal
  }
}

function openAssetLibrary() {
  if (experimentId.value) {
    appRouter.push({ name: 'asset-library', params: { experimentId: experimentId.value } })
  }
}

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
  send,
} = useExperimentDetail(() => experimentId.value)

// Terminal
const TERMINAL_HEIGHT_KEY = 'research-lab-terminal-height'
const terminalOpen = ref(false)
const terminalHeight = ref(getStoredTerminalHeight())
const isResizingTerminal = ref(false)

function getStoredTerminalHeight(): number {
  try {
    const v = Number(localStorage.getItem(TERMINAL_HEIGHT_KEY))
    if (v >= 120 && v <= 600) return v
  } catch { /* ignore */ }
  return 280
}

// Add step dialog
const showAddStep = ref(false)
const newStepName = ref('')
const addingStep = ref(false)
const stepNameInput = ref<HTMLInputElement | null>(null)

function scrollToStep(stepName: string) {
  const el = document.getElementById(`step-${stepName}`)
  el?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

const overallStatus = computed(() => {
  if (!experiment.value) return 'pending'
  const s = experiment.value.steps.map((s) => s.status)
  if (s.some((x) => x === 'failed')) return 'failed'
  if (s.some((x) => x === 'running')) return 'running'
  if (s.length > 0 && s.every((x) => x === 'completed')) return 'completed'
  return 'pending'
})

const runAllDisabled = computed(() => anyStepRunning.value || pipelineRunning.value)

// Push experiment context to the shared toolbar store
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
        onRefreshDetail: () => {
          const id = experimentId.value
          if (id) {
            fetchExperiment(id)
            fetchResults(id)
          }
        },
      })
    } else {
      toolbarCtx.clearContext()
    }
  },
  { immediate: true },
)

onUnmounted(() => {
  toolbarCtx.clearContext()
})

// Fetch asset count when experiment or results change
watch(
  [experimentId, results],
  () => {
    const id = experimentId.value
    if (id) fetchAssetCount(id)
  },
  { immediate: true },
)

function onTerminalResizeStart(e: MouseEvent) {
  isResizingTerminal.value = true
  const startY = e.clientY
  const startH = terminalHeight.value
  function onMove(ev: MouseEvent) {
    terminalHeight.value = Math.max(120, Math.min(600, startH + (startY - ev.clientY)))
  }
  function onUp() {
    isResizingTerminal.value = false
    document.removeEventListener('mousemove', onMove)
    document.removeEventListener('mouseup', onUp)
    try {
      localStorage.setItem(TERMINAL_HEIGHT_KEY, String(terminalHeight.value))
    } catch { /* ignore */ }
  }
  document.addEventListener('mousemove', onMove)
  document.addEventListener('mouseup', onUp)
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

function openAddStep() {
  showAddStep.value = true
  newStepName.value = ''
  setTimeout(() => stepNameInput.value?.focus(), 50)
}

// Keyboard shortcuts scoped to this view
function onKeydown(e: KeyboardEvent) {
  // Ctrl+Shift+Enter: Run pipeline
  if (e.ctrlKey && e.shiftKey && e.key === 'Enter') {
    e.preventDefault()
    if (!runAllDisabled.value) runPipeline()
    return
  }
  // Ctrl+`: Toggle terminal
  if (e.ctrlKey && e.key === '`') {
    e.preventDefault()
    terminalOpen.value = !terminalOpen.value
    return
  }
}

onMounted(() => {
  document.addEventListener('keydown', onKeydown)
})

onUnmounted(() => {
  document.removeEventListener('keydown', onKeydown)
})
</script>

<template>
  <!-- No experiment selected -->
  <div v-if="!experimentId" class="detail-empty">
    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="color: var(--c-fg-dim)">
      <path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>
    <p class="detail-empty__title">Select an experiment</p>
    <p class="detail-empty__subtitle">Or create one from the sidebar</p>
  </div>

  <!-- Loading -->
  <div v-else-if="loading && !experiment" class="detail-loading">
    <svg class="animate-spin" width="16" height="16" viewBox="0 0 24 24" fill="none" style="color: var(--c-fg-dim)">
      <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="2" opacity="0.25"/>
      <path d="M4 12a8 8 0 018-8" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
    </svg>
    <span>Loading experiment...</span>
  </div>

  <!-- Experiment detail -->
  <div v-else-if="experiment" class="detail">
    <!-- Add Step inline form -->
    <div v-if="showAddStep" class="detail__add-step animate-slide-up">
      <div class="detail__add-step-row">
        <span class="detail__add-step-label">Step name:</span>
        <input
          ref="stepNameInput"
          v-model="newStepName"
          class="detail__add-step-input"
          placeholder="e.g., train, evaluate, preprocess..."
          @keydown.enter="doAddStep"
          @keydown.escape="showAddStep = false"
        />
        <button
          class="detail__add-step-submit"
          :disabled="!newStepName.trim() || addingStep"
          @click="doAddStep"
        >{{ addingStep ? '...' : 'Add' }}</button>
        <button class="detail__add-step-cancel" @click="showAddStep = false">
          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M18 6L6 18M6 6l12 12" stroke-linecap="round"/>
          </svg>
        </button>
      </div>
    </div>

    <!-- Pipeline bar with assets toggle -->
    <div class="detail__pipeline">
      <div class="detail__pipeline-top">
        <PipelineBar
          :steps="experiment.steps"
          :results="results"
          @click-step="scrollToStep"
        />
        <button
          class="detail__assets-btn"
          @click="openAssetLibrary"
          title="Browse all experiment assets"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <rect x="3" y="3" width="7" height="7" rx="1"/>
            <rect x="14" y="3" width="7" height="7" rx="1"/>
            <rect x="3" y="14" width="7" height="7" rx="1"/>
            <rect x="14" y="14" width="7" height="7" rx="1"/>
          </svg>
          Assets
          <span v-if="assetCount > 0" class="detail__assets-badge">{{ assetCount }}</span>
        </button>
      </div>
    </div>

    <!-- Step cards -->
    <div class="detail__steps">
      <!-- Empty: no steps -->
      <div v-if="experiment.steps.length === 0" class="detail__steps-empty">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="color: var(--c-fg-dim)">
          <path d="M12 5v14m-7-7h14" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        <p style="color: var(--c-fg-muted)">No steps yet</p>
        <p style="color: var(--c-fg-dim); font-size: 0.75rem">Add steps via the button above, CLI, or MCP</p>
      </div>

      <!-- Step list -->
      <div v-else class="detail__steps-list">
        <StepCanvas
          v-for="(step, index) in experiment.steps"
          :key="step.name"
          :id="`step-${step.name}`"
          :step="step"
          :result="results[step.name]"
          :canvases="canvases[step.name] ?? []"
          :output-lines="outputLines[step.name] ?? []"
          :live-metrics="liveMetrics[step.name] ?? {}"
          :progress="progress[step.name]"
          :style="{ animationDelay: index * 30 + 'ms' }"
          class="detail__step-card"
          @run="runStep(step.name)"
          @stop="stopStep(step.name)"
          @update-code="(code: string) => updateStepCode(step.name, code)"
        />
      </div>
    </div>

    <!-- Terminal panel (collapsible bottom) -->
    <template v-if="terminalOpen">
      <div
        class="detail__terminal-handle"
        :class="{ 'detail__terminal-handle--active': isResizingTerminal }"
        @mousedown="onTerminalResizeStart"
      />
      <div class="detail__terminal" :style="{ height: terminalHeight + 'px' }">
        <TerminalPanel />
      </div>
    </template>
  </div>
</template>

<style scoped>
/* Empty / loading states */
.detail-empty,
.detail-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  gap: 0.75rem;
}

.detail-empty__title {
  font-size: 0.875rem;
  color: var(--c-fg-muted);
  margin: 0;
}

.detail-empty__subtitle {
  font-size: 0.75rem;
  color: var(--c-fg-dim);
  margin: 0;
}

.detail-loading {
  flex-direction: row;
  font-size: 0.875rem;
  color: var(--c-fg-dim);
  gap: 0.5rem;
}

/* Detail layout */
.detail {
  display: flex;
  flex-direction: column;
  height: 100%;
}

/* Add step form */
.detail__add-step {
  flex-shrink: 0;
  padding: 0.5rem 1rem;
  border-bottom: 1px solid var(--c-border);
  background: var(--c-bg1);
}

.detail__add-step-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.detail__add-step-label {
  font-size: 0.75rem;
  color: var(--c-fg-muted);
  white-space: nowrap;
}

.detail__add-step-input {
  flex: 1;
  font-size: 0.75rem;
  padding: 0.25rem 0.5rem;
  background: var(--c-bg-hard);
  color: var(--c-fg);
  border: 1px solid var(--c-border);
  border-radius: var(--radius-sm);
  outline: none;
}

.detail__add-step-input:focus {
  border-color: var(--c-aqua);
}

.detail__add-step-submit {
  font-size: 0.75rem;
  padding: 0.25rem 0.5rem;
  background: var(--c-aqua);
  color: var(--c-bg-hard);
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
  flex-shrink: 0;
}

.detail__add-step-submit:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.detail__add-step-cancel {
  display: flex;
  align-items: center;
  padding: 0.25rem;
  color: var(--c-fg-dim);
  background: transparent;
  border: none;
  cursor: pointer;
}

/* Pipeline */
.detail__pipeline {
  flex-shrink: 0;
  border-bottom: 1px solid var(--c-border);
  background: var(--c-surface);
}

.detail__pipeline-top {
  display: flex;
  align-items: center;
}

.detail__pipeline-top > :first-child {
  flex: 1;
  min-width: 0;
}

.detail__assets-btn {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  padding: 0.25rem 0.75rem;
  margin-right: 0.75rem;
  font-size: 0.75rem;
  font-weight: 500;
  color: var(--c-fg-muted);
  background: var(--c-bg1);
  border: 1px solid var(--c-border);
  border-radius: var(--radius-sm);
  cursor: pointer;
  white-space: nowrap;
  flex-shrink: 0;
  transition: border-color 0.12s, color 0.12s, background 0.12s;
}

.detail__assets-btn:hover {
  border-color: var(--c-fg-dim);
  color: var(--c-fg);
  background: var(--c-surface-hover);
}

.detail__assets-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 1.25rem;
  height: 1rem;
  padding: 0 0.25rem;
  font-size: 0.625rem;
  font-weight: 600;
  font-family: var(--font-mono);
  color: var(--c-bg-hard);
  background: var(--c-aqua);
  border-radius: 0.5rem;
}

/* Steps area */
.detail__steps {
  flex: 1;
  overflow-y: auto;
  padding: 1rem;
}

.detail__steps-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 3rem 0;
  gap: 0.5rem;
  font-size: 0.875rem;
}

.detail__steps-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  max-width: 87.5rem;
}

.detail__step-card {
  animation: slide-up 0.15s ease both;
}

/* Terminal */
.detail__terminal-handle {
  flex-shrink: 0;
  height: 3px;
  cursor: row-resize;
  background: transparent;
  transition: background 0.12s;
}

.detail__terminal-handle:hover,
.detail__terminal-handle--active {
  background: var(--c-aqua);
}

.detail__terminal {
  flex-shrink: 0;
  border-top: 1px solid var(--c-border);
}
</style>
