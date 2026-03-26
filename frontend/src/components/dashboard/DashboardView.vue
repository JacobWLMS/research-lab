<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import type {
  Experiment,
  StepResult,
  CanvasData,
  CanvasWidget,
  ChartWidget,
  ImageWidgetData,
} from '../../types'
import MetricStrip from '../widgets/MetricStrip.vue'
import PlotlyChart from '../widgets/PlotlyChart.vue'
import StreamingOutput from '../shared/StreamingOutput.vue'

const props = defineProps<{
  experimentId: string
  experiment: Experiment
  results: Record<string, StepResult>
  canvases: Record<string, CanvasData[]>
  outputLines: Record<string, string[]>
  liveMetrics: Record<string, Record<string, number | string>>
  progress: Record<string, { current: number; total: number; eta_s?: number }>
}>()

const emit = defineEmits<{
  clickStep: [name: string]
}>()

// Cache for lazily-loaded full step data (canvases with full Plotly JSON / images)
const fullStepData = ref<Record<string, CanvasData[]>>({})
const loadingSteps = ref<Set<string>>(new Set())

// Aggregate all metrics from all completed steps
const allMetrics = computed<Record<string, number | string>>(() => {
  const m: Record<string, number | string> = {}
  for (const [stepName, result] of Object.entries(props.results)) {
    if (result.metrics) {
      Object.assign(m, result.metrics)
    }
  }
  // Merge live metrics
  for (const [stepName, metrics] of Object.entries(props.liveMetrics)) {
    Object.assign(m, metrics)
  }
  return m
})

const hasMetrics = computed(() => Object.keys(allMetrics.value).length > 0)

// Collect all chart widgets from all canvases across all steps
const allCharts = computed(() => {
  const charts: { stepName: string; canvasName: string; widget: ChartWidget }[] = []
  // Use full step data first, fall back to canvas summaries
  const sources = { ...props.canvases, ...fullStepData.value }
  for (const [stepName, canvasList] of Object.entries(sources)) {
    for (const canvas of canvasList) {
      for (const widget of canvas.widgets) {
        if (widget.kind === 'chart') {
          charts.push({
            stepName,
            canvasName: canvas.name,
            widget: widget as ChartWidget,
          })
        }
      }
    }
  }
  return charts
})

// Collect all image widgets from all canvases + result images
const allImages = computed(() => {
  const images: { stepName: string; title: string; src: string }[] = []
  const sources = { ...props.canvases, ...fullStepData.value }

  // Images from canvases
  for (const [stepName, canvasList] of Object.entries(sources)) {
    for (const canvas of canvasList) {
      for (const widget of canvas.widgets) {
        if (widget.kind === 'image') {
          const img = widget as ImageWidgetData
          if (img.data && img.data.length > 100 && !img.data.startsWith('[')) {
            images.push({
              stepName,
              title: img.title || 'Image',
              src: `data:${img.mime};base64,${img.data}`,
            })
          }
        }
      }
    }
  }

  // Images from step results
  for (const [stepName, result] of Object.entries(props.results)) {
    if (result.images) {
      for (const img of result.images) {
        if (img.data && img.data.length > 100 && !img.data.startsWith('[')) {
          // Avoid duplicates -- check if we already have this image from canvas
          const src = `data:${img.mime};base64,${img.data}`
          if (!images.some(i => i.stepName === stepName && i.src === src)) {
            images.push({
              stepName,
              title: img.label || 'Image',
              src,
            })
          }
        }
      }
    }
  }

  return images
})

// Currently running step's output
const runningStep = computed(() => {
  return props.experiment.steps.find(s => s.status === 'running') ?? null
})

const runningStepLines = computed(() => {
  if (!runningStep.value) return []
  return props.outputLines[runningStep.value.name] ?? []
})

const runningProgress = computed(() => {
  if (!runningStep.value) return null
  return props.progress[runningStep.value.name] ?? null
})

const progressPct = computed(() => {
  if (!runningProgress.value || runningProgress.value.total <= 0) return 0
  return Math.min(100, (runningProgress.value.current / runningProgress.value.total) * 100)
})

function fmtEta(s?: number): string {
  if (!s || s <= 0) return ''
  if (s < 60) return `~${Math.ceil(s)}s`
  const m = Math.floor(s / 60)
  const sec = Math.ceil(s % 60)
  return `~${m}m ${sec}s`
}

// Lazily fetch full step data for completed steps (canvases may only have summaries)
async function fetchFullStepData(stepName: string) {
  if (fullStepData.value[stepName] || loadingSteps.value.has(stepName)) return
  loadingSteps.value.add(stepName)
  try {
    const res = await fetch(`/api/experiments/${props.experimentId}/steps/${stepName}`)
    if (!res.ok) return
    const data = await res.json()
    const rawCanvases: Array<{ canvas_name?: string; name?: string; widgets: CanvasWidget[] }> =
      data.canvases ?? []
    if (rawCanvases.length > 0) {
      fullStepData.value = {
        ...fullStepData.value,
        [stepName]: rawCanvases.map(c => ({
          name: c.canvas_name ?? c.name ?? 'Canvas',
          widgets: c.widgets ?? [],
        })),
      }
    }
  } catch {
    // non-fatal
  } finally {
    loadingSteps.value.delete(stepName)
  }
}

// When results change, lazily load full canvas data for completed steps
watch(
  () => props.results,
  (newResults) => {
    for (const [stepName, result] of Object.entries(newResults)) {
      if (result.status === 'completed') {
        fetchFullStepData(stepName)
      }
    }
  },
  { immediate: true, deep: true },
)

// Overall experiment status
const overallStatus = computed(() => {
  const steps = props.experiment.steps
  if (steps.some(s => s.status === 'running')) return 'running'
  if (steps.some(s => s.status === 'failed')) return 'failed'
  if (steps.length > 0 && steps.every(s => s.status === 'completed')) return 'completed'
  return 'pending'
})

const completedCount = computed(() => props.experiment.steps.filter(s => s.status === 'completed').length)
const totalSteps = computed(() => props.experiment.steps.length)
</script>

<template>
  <div class="dashboard">
    <!-- Header -->
    <div class="dashboard__header">
      <h2 class="dashboard__title">{{ experiment.name }}</h2>
      <div class="dashboard__meta">
        <span
          class="dashboard__status-dot"
          :style="{
            background: overallStatus === 'running' ? 'var(--c-yellow)' :
                         overallStatus === 'completed' ? 'var(--c-green)' :
                         overallStatus === 'failed' ? 'var(--c-red)' : 'var(--c-fg-dim)'
          }"
        />
        <span class="dashboard__step-count">{{ completedCount }}/{{ totalSteps }} steps</span>
      </div>
    </div>

    <div class="dashboard__body">
      <!-- Running progress -->
      <div v-if="runningStep" class="dashboard__section dashboard__running">
        <div class="dashboard__section-header">
          <svg class="animate-pulse-glow" width="10" height="10" viewBox="0 0 24 24" fill="var(--c-yellow)"><circle cx="12" cy="12" r="8"/></svg>
          <span>Running: {{ runningStep.title || runningStep.name }}</span>
        </div>
        <div v-if="runningProgress && runningProgress.total > 0" class="dashboard__progress">
          <div class="dashboard__progress-info">
            <span class="dashboard__progress-count">{{ runningProgress.current }}/{{ runningProgress.total }}</span>
            <span class="dashboard__progress-eta">{{ fmtEta(runningProgress.eta_s) }}</span>
          </div>
          <div class="dashboard__progress-bar">
            <div class="dashboard__progress-fill" :style="{ width: progressPct + '%' }" />
          </div>
        </div>
        <StreamingOutput :lines="runningStepLines" />
      </div>

      <!-- Key Metrics -->
      <div v-if="hasMetrics" class="dashboard__section">
        <div class="dashboard__section-header">
          <span>Key Metrics</span>
        </div>
        <MetricStrip :data="allMetrics" />
      </div>

      <!-- Charts -->
      <div v-if="allCharts.length > 0" class="dashboard__section">
        <div class="dashboard__section-header">
          <span>Charts</span>
          <span class="dashboard__count">{{ allCharts.length }}</span>
        </div>
        <div class="dashboard__charts-grid">
          <div
            v-for="(chart, i) in allCharts"
            :key="`chart-${i}`"
            class="dashboard__chart-card"
            @click="emit('clickStep', chart.stepName)"
          >
            <PlotlyChart :plotly-json="chart.widget.plotly_json" :title="chart.widget.title" />
            <span class="dashboard__chart-step">{{ chart.stepName }}</span>
          </div>
        </div>
      </div>

      <!-- Images -->
      <div v-if="allImages.length > 0" class="dashboard__section">
        <div class="dashboard__section-header">
          <span>Images</span>
          <span class="dashboard__count">{{ allImages.length }}</span>
        </div>
        <div class="dashboard__image-grid">
          <div
            v-for="(img, i) in allImages"
            :key="`img-${i}`"
            class="dashboard__image-card"
            @click="emit('clickStep', img.stepName)"
          >
            <img :src="img.src" :alt="img.title" loading="lazy" />
            <div class="dashboard__image-info">
              <span class="dashboard__image-title">{{ img.title }}</span>
              <span class="dashboard__image-step">{{ img.stepName }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Empty state when no results yet -->
      <div
        v-if="!hasMetrics && allCharts.length === 0 && allImages.length === 0 && !runningStep"
        class="dashboard__empty"
      >
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="color: var(--c-fg-dim)">
          <polygon points="12 2 22 8.5 22 15.5 12 22 2 15.5 2 8.5 12 2"/>
        </svg>
        <span>No results yet</span>
        <span class="dashboard__empty-hint">Run the pipeline or individual steps to see results here</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.dashboard {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

.dashboard__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--mc-panel-pad) var(--mc-gap-md);
  border-bottom: var(--mc-panel-border);
  flex-shrink: 0;
}

.dashboard__title {
  margin: 0;
  font-size: var(--mc-body-size);
  font-weight: 600;
  color: var(--c-fg);
}

.dashboard__meta {
  display: flex;
  align-items: center;
  gap: 0.375rem;
}

.dashboard__status-dot {
  width: 0.4375rem;
  height: 0.4375rem;
  border-radius: 50%;
  flex-shrink: 0;
}

.dashboard__step-count {
  font-size: var(--mc-label-size);
  font-family: var(--font-mono);
  color: var(--c-fg-muted);
}

.dashboard__body {
  flex: 1;
  overflow-y: auto;
  padding: var(--mc-gap-sm);
  display: flex;
  flex-direction: column;
  gap: var(--mc-gap-sm);
}

/* Sections */
.dashboard__section {
  background: var(--c-surface);
  border: 1px solid var(--c-border-subtle);
  border-radius: var(--radius-sm);
  overflow: hidden;
}

.dashboard__section-header {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  padding: 0.375rem var(--mc-panel-pad);
  font-size: var(--mc-label-size);
  font-weight: 600;
  color: var(--c-fg-muted);
  border-bottom: 1px solid var(--c-border-subtle);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.dashboard__count {
  font-family: var(--font-mono);
  font-size: 0.5625rem;
  color: var(--c-fg-dim);
}

/* Running section */
.dashboard__running .dashboard__section-header {
  color: var(--c-yellow);
}

/* Progress */
.dashboard__progress {
  padding: var(--mc-panel-pad);
  padding-bottom: 0;
}

.dashboard__progress-info {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.25rem;
}

.dashboard__progress-count {
  font-size: 0.75rem;
  font-family: var(--font-mono);
  color: var(--c-fg-muted);
}

.dashboard__progress-eta {
  font-size: 0.75rem;
  color: var(--c-fg-dim);
}

.dashboard__progress-bar {
  height: 0.25rem;
  background: var(--c-bg2);
  border-radius: var(--radius-sm);
  overflow: hidden;
}

.dashboard__progress-fill {
  height: 100%;
  background: var(--c-aqua);
  transition: width 0.3s ease-out;
  border-radius: var(--radius-sm);
}

/* Charts grid */
.dashboard__charts-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 1px;
  background: var(--c-border-subtle);
}

.dashboard__chart-card {
  background: var(--c-surface);
  cursor: pointer;
  position: relative;
  min-height: 17.5rem;
  transition: background 0.08s;
}

.dashboard__chart-card:hover {
  background: var(--c-surface-hover);
}

.dashboard__chart-card :deep(.w-full) {
  min-height: 17.5rem;
  height: 17.5rem;
}

/* Single chart gets full width */
.dashboard__chart-card:only-child {
  grid-column: 1 / -1;
}

.dashboard__chart-card:only-child :deep(.w-full) {
  height: 22rem;
}

.dashboard__chart-step {
  position: absolute;
  bottom: 0.25rem;
  right: 0.375rem;
  font-size: 0.5625rem;
  font-family: var(--font-mono);
  color: var(--c-fg-dim);
  background: var(--c-bg);
  padding: 0.0625rem 0.25rem;
  border-radius: var(--radius-sm);
  opacity: 0;
  transition: opacity 0.12s;
}

.dashboard__chart-card:hover .dashboard__chart-step {
  opacity: 1;
}

/* Image grid */
.dashboard__image-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(7.5rem, 1fr));
  gap: var(--mc-gap-xs);
  padding: var(--mc-panel-pad);
}

.dashboard__image-card {
  border: 1px solid var(--c-border-subtle);
  border-radius: var(--radius-sm);
  overflow: hidden;
  cursor: pointer;
  transition: border-color 0.12s;
}

.dashboard__image-card:hover {
  border-color: var(--c-fg-dim);
}

.dashboard__image-card img {
  width: 100%;
  aspect-ratio: 1;
  object-fit: cover;
  display: block;
}

.dashboard__image-info {
  padding: 0.1875rem 0.25rem;
  display: flex;
  flex-direction: column;
  gap: 0.0625rem;
}

.dashboard__image-title {
  font-size: 0.5625rem;
  color: var(--c-fg);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.dashboard__image-step {
  font-size: 0.5rem;
  font-family: var(--font-mono);
  color: var(--c-fg-dim);
}

/* Empty state */
.dashboard__empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 3rem 0;
  gap: 0.5rem;
  font-size: var(--mc-body-size);
  color: var(--c-fg-dim);
}

.dashboard__empty-hint {
  font-size: var(--mc-label-size);
  color: var(--c-fg-dim);
  opacity: 0.7;
}

/* Responsive: single column charts on narrow screens */
@media (max-width: 900px) {
  .dashboard__charts-grid {
    grid-template-columns: 1fr;
  }
}
</style>
