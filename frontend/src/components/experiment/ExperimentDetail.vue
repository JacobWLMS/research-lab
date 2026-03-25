<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRoute } from 'vue-router'
import { useExperimentDetail } from '../../composables/useExperimentDetail'
import PipelineBar from './PipelineBar.vue'
import StepCanvas from './StepCanvas.vue'
import StatusBadge from '../shared/StatusBadge.vue'
import TerminalPanel from '../shared/TerminalPanel.vue'

const props = defineProps<{
  id?: string
}>()

const route = useRoute()
const experimentId = computed(() => props.id ?? (route.params.id as string | undefined) ?? null)

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
  send,
} = useExperimentDetail(() => experimentId.value)

// Terminal
const terminalOpen = ref(false)
const terminalHeight = ref(280)
const isResizingTerminal = ref(false)

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
</script>

<template>
  <!-- No experiment selected -->
  <div
    v-if="!experimentId"
    class="flex flex-col items-center justify-center h-full gap-3"
  >
    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="color: var(--color-fg-dim)">
      <path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>
    <p class="text-sm" style="color: var(--color-fg-muted)">Select an experiment</p>
    <p class="text-xs" style="color: var(--color-fg-dim)">Or create one from the sidebar</p>
  </div>

  <!-- Loading -->
  <div
    v-else-if="loading && !experiment"
    class="flex items-center justify-center h-full text-sm"
    style="color: var(--color-fg-dim)"
  >
    <svg class="animate-spin mr-2 h-4 w-4" viewBox="0 0 24 24" fill="none">
      <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="2" opacity="0.25"/>
      <path d="M4 12a8 8 0 018-8" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
    </svg>
    Loading...
  </div>

  <!-- Experiment detail -->
  <div v-else-if="experiment" class="flex flex-col h-full">
    <!-- Header row -->
    <div
      class="shrink-0 flex items-center gap-3 px-4 py-2 border-b"
      style="background: var(--color-bg); border-color: var(--color-bg2)"
    >
      <StatusBadge :status="overallStatus" />
      <h1 class="text-sm font-semibold" style="color: var(--color-fg)">{{ experiment.name }}</h1>
      <span class="text-xs font-mono" style="color: var(--color-fg-dim)">{{ experiment.id }}</span>
      <div class="flex-1" />

      <!-- Run Pipeline -->
      <button
        class="flex items-center gap-1 px-3 py-1 text-xs font-medium cursor-pointer"
        :style="{
          background: runAllDisabled ? 'var(--color-bg2)' : 'var(--color-aqua)',
          color: runAllDisabled ? 'var(--color-fg-dim)' : 'var(--color-bg-hard)',
          opacity: runAllDisabled ? 0.5 : 1,
          cursor: runAllDisabled ? 'not-allowed' : 'pointer',
          borderRadius: '2px',
        }"
        :disabled="runAllDisabled"
        @click="!runAllDisabled && runPipeline()"
      >
        <svg v-if="pipelineRunning" class="animate-spin h-3 w-3" viewBox="0 0 24 24" fill="none">
          <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="2.5" opacity="0.3"/>
          <path d="M4 12a8 8 0 018-8" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"/>
        </svg>
        <svg v-else width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>
        {{ pipelineRunning ? 'Running...' : 'Run Pipeline' }}
      </button>

      <!-- Add Step -->
      <button
        class="flex items-center gap-1 px-3 py-1 text-xs font-medium cursor-pointer"
        style="background: var(--color-bg1); color: var(--color-fg-muted); border-radius: 2px; transition: background 0.12s"
        @click="openAddStep"
        @mouseenter="($event.currentTarget as HTMLElement).style.background = 'var(--color-bg2)'"
        @mouseleave="($event.currentTarget as HTMLElement).style.background = 'var(--color-bg1)'"
      >
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M12 5v14m-7-7h14" stroke-linecap="round"/>
        </svg>
        Add Step
      </button>

      <!-- Terminal toggle -->
      <button
        class="flex items-center gap-1 px-3 py-1 text-xs font-medium cursor-pointer"
        :style="{
          background: terminalOpen ? 'var(--color-bg2)' : 'var(--color-bg1)',
          color: terminalOpen ? 'var(--color-fg)' : 'var(--color-fg-muted)',
          borderRadius: '2px',
          transition: 'all 0.12s',
        }"
        @click="terminalOpen = !terminalOpen"
      >
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="4 17 10 11 4 5"/>
          <line x1="12" y1="19" x2="20" y2="19"/>
        </svg>
        Terminal
      </button>
    </div>

    <!-- Add Step inline form -->
    <div
      v-if="showAddStep"
      class="shrink-0 px-4 py-2 border-b animate-slide-up"
      style="border-color: var(--color-bg2); background: var(--color-bg1)"
    >
      <div class="flex items-center gap-2">
        <span class="text-xs" style="color: var(--color-fg-muted)">Step name:</span>
        <input
          ref="stepNameInput"
          v-model="newStepName"
          class="flex-1 text-xs px-2 py-1 outline-none border"
          style="background: var(--color-bg-hard); color: var(--color-fg); border-color: var(--color-bg2); border-radius: 2px"
          placeholder="e.g., train, evaluate, preprocess..."
          @keydown.enter="doAddStep"
          @keydown.escape="showAddStep = false"
        />
        <button
          class="text-xs px-2 py-1 cursor-pointer shrink-0"
          :style="{
            background: !newStepName.trim() || addingStep ? 'var(--color-bg2)' : 'var(--color-aqua)',
            color: !newStepName.trim() || addingStep ? 'var(--color-fg-dim)' : 'var(--color-bg-hard)',
            borderRadius: '2px',
            opacity: !newStepName.trim() || addingStep ? 0.5 : 1,
          }"
          :disabled="!newStepName.trim() || addingStep"
          @click="doAddStep"
        >{{ addingStep ? '...' : 'Add' }}</button>
        <button
          class="text-xs px-1 py-1 cursor-pointer"
          style="color: var(--color-fg-dim); background: transparent"
          @click="showAddStep = false"
        >
          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M18 6L6 18M6 6l12 12" stroke-linecap="round"/>
          </svg>
        </button>
      </div>
    </div>

    <!-- Pipeline bar -->
    <div class="shrink-0 border-b" style="background: var(--color-bg); border-color: var(--color-bg2)">
      <PipelineBar
        :steps="experiment.steps"
        :results="results"
        @click-step="scrollToStep"
      />
    </div>

    <!-- Step cards -->
    <div class="flex-1 overflow-y-auto p-4">
      <!-- Empty: no steps -->
      <div
        v-if="experiment.steps.length === 0"
        class="flex flex-col items-center justify-center py-12 gap-2"
      >
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="color: var(--color-fg-dim)">
          <path d="M12 5v14m-7-7h14" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        <p class="text-sm" style="color: var(--color-fg-muted)">No steps yet</p>
        <p class="text-xs" style="color: var(--color-fg-dim)">Add steps via the button above, CLI, or MCP</p>
      </div>

      <!-- Step list -->
      <div v-else class="flex flex-col gap-3 max-w-[1400px]">
        <StepCanvas
          v-for="step in experiment.steps"
          :key="step.name"
          :id="`step-${step.name}`"
          :step="step"
          :result="results[step.name]"
          :canvases="canvases[step.name] ?? []"
          :output-lines="outputLines[step.name] ?? []"
          :live-metrics="liveMetrics[step.name] ?? {}"
          :progress="progress[step.name]"
          @run="runStep(step.name)"
          @stop="stopStep(step.name)"
          @update-code="(code: string) => updateStepCode(step.name, code)"
        />
      </div>
    </div>

    <!-- Terminal panel (collapsible bottom) -->
    <template v-if="terminalOpen">
      <div
        class="shrink-0 h-1 cursor-row-resize"
        :style="{
          background: isResizingTerminal ? 'var(--color-aqua)' : 'var(--color-bg2)',
          transition: 'background 0.12s',
        }"
        @mousedown="onTerminalResizeStart"
        @mouseenter="($event.currentTarget as HTMLElement).style.background = 'var(--color-aqua)'"
        @mouseleave="!isResizingTerminal && (($event.currentTarget as HTMLElement).style.background = 'var(--color-bg2)')"
      />
      <div
        class="shrink-0 border-t"
        :style="{ height: terminalHeight + 'px', borderColor: 'var(--color-bg2)' }"
      >
        <TerminalPanel />
      </div>
    </template>
  </div>
</template>
