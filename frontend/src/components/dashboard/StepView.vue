<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import type {
  Step,
  StepResult,
  CanvasData,
  CanvasWidget,
  ChartWidget,
  ImageWidgetData,
} from '../../types'
import { useRunHistory } from '../../composables/useRunHistory'
import StatusBadge from '../shared/StatusBadge.vue'
import StreamingOutput from '../shared/StreamingOutput.vue'
import CodeBlock from '../shared/CodeBlock.vue'
import MetricStrip from '../widgets/MetricStrip.vue'
import PlotlyChart from '../widgets/PlotlyChart.vue'
import ImageWidget from '../widgets/ImageWidget.vue'
import TextBlock from '../widgets/TextBlock.vue'

const props = defineProps<{
  experimentId: string
  step: Step | null
  result?: StepResult
  canvases: CanvasData[]
  outputLines: string[]
  liveMetrics: Record<string, number | string>
  progress?: { current: number; total: number; eta_s?: number }
}>()

const emit = defineEmits<{
  run: []
  stop: []
  updateCode: [code: string]
  navigateDashboard: []
}>()

const router = useRouter()
const route = useRoute()
const showCode = ref(false)
const showLogs = ref(false)

// Lazily fetched full canvas data (in case the canvases prop only has summaries)
const fullCanvases = ref<CanvasData[]>([])
const loadingFull = ref(false)

const stepName = computed(() => props.step?.name ?? '')

// --- Run history ---
const {
  runs,
  selectedRun,
  runResult: historyResult,
  runCanvases: historyCanvases,
  isViewingOldRun,
  fetchHistory,
  selectRun,
} = useRunHistory(
  () => props.experimentId || null,
  () => stepName.value,
)

// Fetch history when result changes
watch(
  () => props.result?.run_number,
  () => {
    if (props.experimentId && props.result) {
      fetchHistory()
      selectedRun.value = null
    }
  },
  { immediate: true },
)

// Active result/canvases: use history override when viewing an old run
const activeResult = computed<StepResult | undefined>(() => {
  if (selectedRun.value !== null && historyResult.value) {
    return historyResult.value
  }
  return props.result
})

const activeCanvases = computed<CanvasData[]>(() => {
  if (selectedRun.value !== null && historyCanvases.value.length > 0) {
    return historyCanvases.value
  }
  // Prefer fully-loaded canvases
  if (fullCanvases.value.length > 0) return fullCanvases.value
  return props.canvases
})

const hasMultipleRuns = computed(() => runs.value.length > 1)

function onRunSelect(e: Event) {
  const val = (e.target as HTMLSelectElement).value
  if (val === 'latest') {
    selectRun(null)
  } else {
    selectRun(Number(val))
  }
}

// Fetch full canvas data lazily for this step
async function fetchFullCanvasData() {
  if (loadingFull.value || !props.experimentId || !stepName.value) return
  loadingFull.value = true
  try {
    const res = await fetch(`/api/experiments/${props.experimentId}/steps/${stepName.value}`)
    if (!res.ok) return
    const data = await res.json()
    const rawCanvases: Array<{ canvas_name?: string; name?: string; widgets: CanvasWidget[] }> =
      data.canvases ?? []
    if (rawCanvases.length > 0) {
      fullCanvases.value = rawCanvases.map(c => ({
        name: c.canvas_name ?? c.name ?? 'Canvas',
        widgets: c.widgets ?? [],
      }))
    }
  } catch {
    // non-fatal
  } finally {
    loadingFull.value = false
  }
}

// Fetch full canvas data when step changes
watch(
  [() => props.experimentId, () => stepName.value, () => props.result?.run_number],
  () => {
    fullCanvases.value = []
    if (props.result?.status === 'completed') {
      fetchFullCanvasData()
    }
  },
  { immediate: true },
)

// Computed helpers
const isRunning = computed(() => props.step?.status === 'running')

const chartWidgets = computed(() => {
  const charts: { canvasName: string; widget: ChartWidget }[] = []
  for (const canvas of activeCanvases.value) {
    for (const widget of canvas.widgets) {
      if (widget.kind === 'chart') {
        charts.push({ canvasName: canvas.name, widget: widget as ChartWidget })
      }
    }
  }
  return charts
})

const imageWidgets = computed(() => {
  const images: { canvasName: string; widget: ImageWidgetData }[] = []
  for (const canvas of activeCanvases.value) {
    for (const widget of canvas.widgets) {
      if (widget.kind === 'image') {
        images.push({ canvasName: canvas.name, widget: widget as ImageWidgetData })
      }
    }
  }
  return images
})

const textWidgets = computed(() => {
  const texts: { canvasName: string; content: string }[] = []
  for (const canvas of activeCanvases.value) {
    for (const widget of canvas.widgets) {
      if (widget.kind === 'text') {
        texts.push({ canvasName: canvas.name, content: (widget as any).content })
      }
    }
  }
  return texts
})

// Combine result metrics + live metrics
const summaryMetrics = computed<Record<string, number | string>>(() => {
  const m: Record<string, number | string> = {}
  if (activeResult.value && activeResult.value.metrics) {
    Object.assign(m, activeResult.value.metrics)
  }
  if (!isViewingOldRun.value && props.liveMetrics) {
    Object.assign(m, props.liveMetrics)
  }
  return m
})

const progressPct = computed(() => {
  if (!props.progress || props.progress.total <= 0) return 0
  return Math.min(100, (props.progress.current / props.progress.total) * 100)
})

const hasCanvases = computed(() => {
  return activeCanvases.value.length > 0 &&
    activeCanvases.value.some(c => c.widgets.length > 0)
})

const runNumber = computed(() => activeResult.value?.run_number ?? 0)

function fmtDur(s: number | undefined): string {
  if (s == null || s < 0) return ''
  if (s < 60) return `${Math.round(s)}s`
  const m = Math.floor(s / 60)
  const sec = Math.round(s % 60)
  return sec > 0 ? `${m}m ${sec}s` : `${m}m`
}

function fmtEta(s?: number): string {
  if (!s || s <= 0) return ''
  if (s < 60) return `~${Math.ceil(s)}s`
  const m = Math.floor(s / 60)
  const sec = Math.ceil(s % 60)
  return `~${m}m ${sec}s`
}

// Strip ANSI escape codes from text
function stripAnsi(text: string): string {
  return text.replace(/\x1b\[[0-9;]*m/g, '')
}

// Format a Python traceback with basic syntax highlighting via HTML spans
function formatTraceback(text: string): string {
  const cleaned = stripAnsi(text)
  const lines = cleaned.split('\n')
  return lines.map((line) => {
    const escaped = line.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    if (/^\s*File\s+"/.test(line)) return `<span class="tb-file">${escaped}</span>`
    if (/^\s*line\s+\d+/.test(line)) return `<span class="tb-lineno">${escaped}</span>`
    if (/^[A-Z]\w*(Error|Exception|Warning)/.test(line)) return `<span class="tb-error-type">${escaped}</span>`
    return escaped
  }).join('\n')
}
</script>

<template>
  <div v-if="!step" class="step-view__empty">
    <span>Step not found</span>
    <button class="step-view__back-btn" @click="emit('navigateDashboard')">Back to dashboard</button>
  </div>

  <div v-else class="step-view">
    <!-- Step header -->
    <div class="step-view__header">
      <div class="step-view__header-left">
        <button class="step-view__back" title="Back to dashboard (Esc)" @click="emit('navigateDashboard')">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M19 12H5m0 0l7 7m-7-7l7-7" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </button>
        <StatusBadge :status="step.status" />
        <span class="step-view__title">{{ step.title || step.name }}</span>
        <span v-if="step.title && step.title !== step.name" class="step-view__name-id">{{ step.name }}</span>
        <span v-if="activeResult && !isRunning" class="step-view__duration">{{ fmtDur(activeResult.execution_time_s) }}</span>

        <!-- Run history dropdown -->
        <select
          v-if="hasMultipleRuns && !isRunning"
          class="step-view__run-select"
          :value="selectedRun === null ? 'latest' : String(selectedRun)"
          @change="onRunSelect"
        >
          <option
            v-for="run in runs"
            :key="run.run_number"
            :value="run.run_number === runs[0].run_number ? 'latest' : String(run.run_number)"
          >
            Run #{{ run.run_number }}{{ run.run_number === runs[0].run_number ? ' (latest)' : '' }}
            {{ run.status === 'failed' ? ' [failed]' : '' }}
          </option>
        </select>
      </div>

      <div class="step-view__header-right">
        <!-- Run / Stop -->
        <button v-if="isRunning" class="step-view__stop-btn" @click="emit('stop')">
          <svg width="10" height="10" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="6" width="12" height="12" rx="1"/></svg>
          Stop
        </button>
        <button v-else class="step-view__run-btn" @click="emit('run')">
          <svg width="10" height="10" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>
          Run Step
        </button>

        <!-- Toggles -->
        <button
          class="step-view__toggle"
          :class="{ 'step-view__toggle--active': showLogs }"
          @click="showLogs = !showLogs"
        >Logs</button>
        <button
          class="step-view__toggle"
          :class="{ 'step-view__toggle--active': showCode }"
          @click="showCode = !showCode"
        >Code</button>
      </div>
    </div>

    <!-- Old run banner -->
    <div v-if="isViewingOldRun" class="step-view__old-run">
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="10"/>
        <polyline points="12 6 12 12 16 14"/>
      </svg>
      Viewing Run #{{ selectedRun }} (not latest)
      <button class="step-view__old-run-dismiss" @click="selectRun(null)">View latest</button>
    </div>

    <!-- Description -->
    <div v-if="step.description" class="step-view__description">{{ step.description }}</div>

    <!-- Body -->
    <div class="step-view__body">
      <!-- Progress bar -->
      <div v-if="progress && progress.total > 0" class="step-view__progress">
        <div class="step-view__progress-info">
          <span class="step-view__progress-count">{{ progress.current }}/{{ progress.total }}</span>
          <span class="step-view__progress-eta">{{ fmtEta(progress.eta_s) }}</span>
        </div>
        <div class="step-view__progress-bar">
          <div
            class="step-view__progress-fill"
            :style="{
              width: progressPct + '%',
              background: step.status === 'failed' ? 'var(--c-red)' : 'var(--c-aqua)',
            }"
          />
        </div>
      </div>

      <!-- Metrics -->
      <div v-if="Object.keys(summaryMetrics).length > 0" class="step-view__metrics">
        <MetricStrip :data="summaryMetrics" />
      </div>

      <!-- Charts (2-column grid) -->
      <div v-if="chartWidgets.length > 0" class="step-view__charts">
        <div
          v-for="(chart, i) in chartWidgets"
          :key="`chart-${i}`"
          class="step-view__chart"
        >
          <PlotlyChart :plotly-json="chart.widget.plotly_json" :title="chart.widget.title" />
        </div>
      </div>

      <!-- Images grid -->
      <div v-if="imageWidgets.length > 0" class="step-view__images">
        <div
          v-for="(img, i) in imageWidgets"
          :key="`img-${i}`"
          class="step-view__image-card"
        >
          <ImageWidget :title="img.widget.title" :mime="img.widget.mime" :data="img.widget.data" />
        </div>
      </div>

      <!-- Text blocks -->
      <div v-if="textWidgets.length > 0" class="step-view__texts">
        <div v-for="(t, i) in textWidgets" :key="`text-${i}`" class="step-view__text">
          <TextBlock :content="t.content" />
        </div>
      </div>

      <!-- Live output (if running) -->
      <div v-if="isRunning || outputLines.length > 0" class="step-view__output">
        <StreamingOutput :lines="outputLines" />
      </div>

      <!-- Error display -->
      <div v-if="activeResult?.error" class="step-view__error">
        <div class="step-view__error-header">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10"/>
            <path d="M12 8v4m0 4h.01" stroke-linecap="round"/>
          </svg>
          Error
        </div>
        <pre class="step-view__error-traceback" v-html="formatTraceback(activeResult.error)" />
      </div>

      <!-- Empty: not yet executed -->
      <div v-if="!activeResult && !isRunning && outputLines.length === 0" class="step-view__empty-body">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="color: var(--c-fg-dim)">
          <circle cx="12" cy="12" r="10"/>
          <polyline points="12 6 12 12 16 14"/>
        </svg>
        <span>Not yet executed</span>
      </div>
    </div>

    <!-- Code block (collapsible) -->
    <div v-if="showCode" class="step-view__code animate-slide-up">
      <CodeBlock
        :code="step.code"
        :editable="!isRunning"
        @update:code="(code: string) => emit('updateCode', code)"
      />
    </div>

    <!-- Logs panel (collapsible) -->
    <div v-if="showLogs" class="step-view__logs animate-slide-up">
      <template v-if="activeResult">
        <div class="step-view__logs-label">Full Output</div>
        <StreamingOutput :lines="activeResult.stdout ? activeResult.stdout.split('\n') : []" />
        <div v-if="activeResult.stderr" class="step-view__logs-section">
          <div class="step-view__logs-label step-view__logs-label--error">Stderr</div>
          <StreamingOutput :lines="activeResult.stderr.split('\n')" />
        </div>
      </template>
      <div v-else class="step-view__logs-empty">No logs available</div>
    </div>
  </div>
</template>

<style scoped>
.step-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

.step-view__empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  gap: 0.5rem;
  font-size: var(--mc-body-size);
  color: var(--c-fg-dim);
}

.step-view__back-btn {
  padding: 0.25rem 0.75rem;
  font-size: var(--mc-label-size);
  color: var(--c-aqua);
  background: var(--c-bg1);
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
}

/* Header */
.step-view__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--mc-panel-pad) var(--mc-gap-md);
  border-bottom: var(--mc-panel-border);
  flex-shrink: 0;
  gap: 0.5rem;
}

.step-view__header-left {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  min-width: 0;
  flex: 1;
}

.step-view__header-right {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  flex-shrink: 0;
}

.step-view__back {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 1.5rem;
  height: 1.5rem;
  color: var(--c-fg-muted);
  background: transparent;
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
  flex-shrink: 0;
  transition: background 0.08s, color 0.08s;
}

.step-view__back:hover {
  background: var(--c-surface-hover);
  color: var(--c-fg);
}

.step-view__title {
  font-size: var(--mc-body-size);
  font-weight: 600;
  color: var(--c-fg);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.step-view__name-id {
  font-size: 0.625rem;
  font-family: var(--font-mono);
  color: var(--c-fg-dim);
  opacity: 0.7;
}

.step-view__duration {
  font-size: 0.75rem;
  font-family: var(--font-mono);
  color: var(--c-fg-dim);
}

/* Run selector */
.step-view__run-select {
  font-size: 0.625rem;
  font-weight: 600;
  font-family: var(--font-mono);
  padding: 0.0625rem 0.375rem;
  background: var(--c-bg2);
  color: var(--c-fg);
  border: 1px solid var(--c-border);
  border-radius: var(--radius-sm);
  cursor: pointer;
  outline: none;
  max-width: 8rem;
}

.step-view__run-select:focus { border-color: var(--c-aqua); }

/* Buttons */
.step-view__run-btn,
.step-view__stop-btn {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.1875rem 0.5rem;
  font-size: var(--mc-label-size);
  font-weight: 500;
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: filter 0.12s;
}

.step-view__run-btn {
  background: var(--c-bg2);
  color: var(--c-fg);
}

.step-view__run-btn:hover {
  background: var(--c-bg3);
}

.step-view__stop-btn {
  background: var(--c-red);
  color: var(--c-bg-hard);
}

.step-view__stop-btn:hover {
  filter: brightness(1.1);
}

/* Toggles */
.step-view__toggle {
  font-size: var(--mc-label-size);
  padding: 0.125rem 0.375rem;
  color: var(--c-fg-muted);
  background: transparent;
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: background 0.08s, color 0.08s;
}

.step-view__toggle:hover {
  background: var(--c-surface-hover);
}

.step-view__toggle--active {
  background: var(--c-surface-active);
  color: var(--c-fg);
}

/* Old run banner */
.step-view__old-run {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  padding: 0.25rem var(--mc-gap-md);
  font-size: var(--mc-label-size);
  color: var(--c-yellow);
  background: color-mix(in srgb, var(--c-yellow) 8%, transparent);
  border-bottom: 1px solid color-mix(in srgb, var(--c-yellow) 20%, transparent);
  flex-shrink: 0;
}

.step-view__old-run-dismiss {
  margin-left: auto;
  font-size: 0.625rem;
  font-weight: 500;
  padding: 0.0625rem 0.375rem;
  color: var(--c-aqua);
  background: transparent;
  border: 1px solid var(--c-aqua);
  border-radius: var(--radius-sm);
  cursor: pointer;
}

/* Description */
.step-view__description {
  padding: 0.25rem var(--mc-gap-md);
  font-size: var(--mc-label-size);
  color: var(--c-fg-muted);
  border-bottom: 1px solid var(--c-border-subtle);
  flex-shrink: 0;
}

/* Body */
.step-view__body {
  flex: 1;
  overflow-y: auto;
  padding: var(--mc-gap-sm) var(--mc-gap-md);
  display: flex;
  flex-direction: column;
  gap: var(--mc-gap-sm);
}

/* Metrics */
.step-view__metrics {
  padding: 0;
}

/* Progress */
.step-view__progress {
  padding: 0;
}

.step-view__progress-info {
  display: flex;
  justify-content: space-between;
  margin-bottom: 0.25rem;
}

.step-view__progress-count {
  font-size: 0.75rem;
  font-family: var(--font-mono);
  color: var(--c-fg-muted);
}

.step-view__progress-eta {
  font-size: 0.75rem;
  color: var(--c-fg-dim);
}

.step-view__progress-bar {
  height: 0.25rem;
  background: var(--c-bg2);
  border-radius: var(--radius-sm);
  overflow: hidden;
}

.step-view__progress-fill {
  height: 100%;
  transition: width 0.3s ease-out;
  border-radius: var(--radius-sm);
}

/* Charts */
.step-view__charts {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--mc-gap-sm);
}

.step-view__chart {
  min-height: 17.5rem;
  border: 1px solid var(--c-border-subtle);
  border-radius: var(--radius-sm);
  overflow: hidden;
}

.step-view__chart :deep(.w-full) {
  min-height: 17.5rem;
  height: 17.5rem;
}

.step-view__chart:only-child {
  grid-column: 1 / -1;
}

.step-view__chart:only-child :deep(.w-full) {
  height: 22rem;
}

/* Images */
.step-view__images {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(10rem, 1fr));
  gap: var(--mc-gap-sm);
}

.step-view__image-card {
  border: 1px solid var(--c-border-subtle);
  border-radius: var(--radius-sm);
  overflow: hidden;
}

/* Texts */
.step-view__texts {
  display: flex;
  flex-direction: column;
  gap: var(--mc-gap-sm);
}

.step-view__text {
  border: 1px solid var(--c-border-subtle);
  border-radius: var(--radius-sm);
  overflow: hidden;
}

/* Output */
.step-view__output {
  border: 1px solid var(--c-border-subtle);
  border-radius: var(--radius-sm);
  overflow: hidden;
  max-height: 12rem;
}

/* Error */
.step-view__error {
  border: 1px solid var(--c-red);
  border-radius: var(--radius-sm);
  overflow: hidden;
}

.step-view__error-header {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  padding: 0.375rem 0.5rem;
  font-size: 0.75rem;
  font-weight: 600;
  background: var(--c-red);
  color: var(--c-bg-hard);
}

.step-view__error-traceback {
  margin: 0;
  padding: 0.5rem;
  font-size: 0.75rem;
  font-family: var(--font-mono);
  background: var(--c-bg-hard);
  color: var(--c-fg2);
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.5;
  overflow-x: auto;
}

.step-view__error-traceback :deep(.tb-file) { color: var(--c-aqua); }
.step-view__error-traceback :deep(.tb-lineno) { color: var(--c-yellow); }
.step-view__error-traceback :deep(.tb-error-type) { color: var(--c-red); font-weight: 600; }

/* Empty body */
.step-view__empty-body {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 3rem 0;
  gap: 0.25rem;
  font-size: 0.75rem;
  color: var(--c-fg-dim);
}

/* Code */
.step-view__code {
  flex-shrink: 0;
  border-top: var(--mc-panel-border);
  max-height: 20rem;
  overflow: auto;
}

/* Logs */
.step-view__logs {
  flex-shrink: 0;
  border-top: var(--mc-panel-border);
  padding: var(--mc-panel-pad);
  max-height: 15rem;
  overflow-y: auto;
}

.step-view__logs-label {
  font-size: 0.75rem;
  font-weight: 500;
  color: var(--c-fg-muted);
  margin-bottom: 0.25rem;
}

.step-view__logs-label--error {
  color: var(--c-red);
}

.step-view__logs-section {
  margin-top: 0.5rem;
}

.step-view__logs-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0.75rem;
  font-size: 0.75rem;
  color: var(--c-fg-dim);
}

/* Responsive */
@media (max-width: 900px) {
  .step-view__charts {
    grid-template-columns: 1fr;
  }
}
</style>
