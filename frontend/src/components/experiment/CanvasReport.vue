<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type {
  Step,
  StepResult,
  CanvasData,
  CanvasWidget,
  ChartWidget,
  MetricsWidget,
  ImageWidgetData,
  TextWidget,
  WsMessage,
} from '../../types'
import { useWebSocket } from '../../composables/useWebSocket'
import StatusBadge from '../shared/StatusBadge.vue'
import PlotlyChart from '../widgets/PlotlyChart.vue'
import MetricStrip from '../widgets/MetricStrip.vue'
import ImageWidget from '../widgets/ImageWidget.vue'
import TextBlock from '../widgets/TextBlock.vue'

const route = useRoute()
const router = useRouter()
const { subscribe } = useWebSocket()

const experimentId = computed(() => route.params.experimentId as string)
const stepName = computed(() => route.params.stepName as string)

const step = ref<Step | null>(null)
const result = ref<StepResult | null>(null)
const canvases = ref<CanvasData[]>([])
const loading = ref(true)
const error = ref<string | null>(null)
const activeCanvasIdx = ref(0)
const ready = ref(false)

const activeCanvas = computed<CanvasData | null>(() => {
  if (canvases.value.length === 0) return null
  return canvases.value[activeCanvasIdx.value] ?? canvases.value[0]
})

function fmtDur(s: number | undefined): string {
  if (!s) return ''
  if (s < 1) return `${(s * 1000).toFixed(0)}ms`
  if (s < 60) return `${s.toFixed(1)}s`
  const m = Math.floor(s / 60)
  const sec = Math.floor(s % 60)
  return `${m}m ${sec}s`
}

function isChart(w: CanvasWidget): w is ChartWidget { return w.kind === 'chart' }
function isMetrics(w: CanvasWidget): w is MetricsWidget { return w.kind === 'metrics' }
function isImage(w: CanvasWidget): w is ImageWidgetData { return w.kind === 'image' }
function isText(w: CanvasWidget): w is TextWidget { return w.kind === 'text' }

async function fetchStepData() {
  loading.value = true
  error.value = null
  try {
    const res = await fetch(`/api/experiments/${experimentId.value}/steps/${stepName.value}`)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = await res.json()
    step.value = data.step
    result.value = data.result ?? null

    // Canvases come from top-level or nested in result
    const rawCanvases: Array<{ canvas_name?: string; name?: string; widgets: CanvasWidget[] }> =
      data.canvases ?? data.result?.canvases ?? []
    canvases.value = rawCanvases.map((c) => ({
      name: c.canvas_name ?? c.name ?? 'Canvas',
      widgets: c.widgets ?? [],
    }))
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    loading.value = false
    // Trigger entrance animation
    requestAnimationFrame(() => { ready.value = true })
  }
}

// Live canvas updates via WebSocket
const unsubscribe = subscribe((msg: WsMessage) => {
  if (msg.type !== 'canvas_update') return
  if (!('experiment_id' in msg) || msg.experiment_id !== experimentId.value) return
  if (msg.step_name !== stepName.value) return

  const canvas: CanvasData = { name: msg.canvas_name, widgets: msg.widgets }
  const idx = canvases.value.findIndex((c) => c.name === msg.canvas_name)
  if (idx >= 0) {
    canvases.value[idx] = canvas
  } else {
    canvases.value.push(canvas)
  }
})

function goBack() {
  router.push({ name: 'experiment', params: { id: experimentId.value } })
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') {
    goBack()
  }
}

onMounted(() => {
  fetchStepData()
  document.addEventListener('keydown', onKeydown)
})

onUnmounted(() => {
  document.removeEventListener('keydown', onKeydown)
  unsubscribe()
})

watch([experimentId, stepName], () => {
  fetchStepData()
})
</script>

<template>
  <div
    class="canvas-report"
    :class="{ 'canvas-report--ready': ready }"
  >
    <!-- Slim header -->
    <header class="canvas-report__header">
      <div class="canvas-report__header-left">
        <button
          class="canvas-report__back"
          @click="goBack"
          title="Back to experiment (Esc)"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M19 12H5m0 0l7 7m-7-7l7-7" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          <span>Back</span>
        </button>

        <div class="canvas-report__divider" />

        <span class="canvas-report__step-label">step:</span>
        <span class="canvas-report__step-name">{{ stepName }}</span>

        <template v-if="step">
          <div class="canvas-report__divider" />
          <StatusBadge :status="step.status" />
        </template>

        <template v-if="result">
          <div class="canvas-report__divider" />
          <span class="canvas-report__duration">{{ fmtDur(result.execution_time_s) }}</span>
        </template>
      </div>

      <div class="canvas-report__header-right">
        <span class="canvas-report__hint">Esc to close</span>
      </div>
    </header>

    <!-- Loading state -->
    <div v-if="loading" class="canvas-report__loading">
      <svg class="animate-spin" width="20" height="20" viewBox="0 0 24 24" fill="none">
        <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="2" opacity="0.25"/>
        <path d="M4 12a8 8 0 018-8" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
      </svg>
      <span>Loading report...</span>
    </div>

    <!-- Error state -->
    <div v-else-if="error" class="canvas-report__error">
      <span>Failed to load: {{ error }}</span>
      <button class="canvas-report__retry" @click="fetchStepData">Retry</button>
    </div>

    <!-- No canvases -->
    <div v-else-if="canvases.length === 0" class="canvas-report__empty">
      <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="color: var(--color-fg-dim)">
        <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
        <path d="M3 9h18M9 21V9" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
      <span>No canvas data for this step</span>
      <button class="canvas-report__back-link" @click="goBack">Go back</button>
    </div>

    <!-- Canvas content -->
    <template v-else>
      <!-- Canvas tabs (if multiple) -->
      <div v-if="canvases.length > 1" class="canvas-report__tabs">
        <button
          v-for="(c, idx) in canvases"
          :key="c.name"
          class="canvas-report__tab"
          :class="{ 'canvas-report__tab--active': idx === activeCanvasIdx }"
          @click="activeCanvasIdx = idx"
        >{{ c.name }}</button>
      </div>

      <!-- Single canvas label (if only one) -->
      <div v-else-if="canvases.length === 1 && canvases[0].name" class="canvas-report__canvas-label">
        {{ canvases[0].name }}
      </div>

      <!-- Widgets area -->
      <div class="canvas-report__body">
        <div v-if="activeCanvas" class="canvas-report__widgets">
          <template v-for="(widget, idx) in activeCanvas.widgets" :key="idx">
            <!-- Chart widget -->
            <div v-if="isChart(widget)" class="canvas-report__widget canvas-report__widget--chart">
              <PlotlyChart
                :plotly-json="widget.plotly_json"
                :title="widget.title"
              />
            </div>

            <!-- Metrics widget -->
            <div v-else-if="isMetrics(widget)" class="canvas-report__widget canvas-report__widget--metrics">
              <MetricStrip :data="widget.data" />
            </div>

            <!-- Image widget -->
            <div v-else-if="isImage(widget)" class="canvas-report__widget canvas-report__widget--image">
              <ImageWidget
                :title="widget.title"
                :mime="widget.mime"
                :data="widget.data"
              />
            </div>

            <!-- Text widget -->
            <div v-else-if="isText(widget)" class="canvas-report__widget canvas-report__widget--text">
              <TextBlock :content="widget.content" />
            </div>
          </template>

          <!-- Empty canvas -->
          <div
            v-if="activeCanvas.widgets.length === 0"
            class="canvas-report__widget-empty"
          >
            This canvas has no widgets yet
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.canvas-report {
  position: fixed;
  inset: 0;
  z-index: 100;
  display: flex;
  flex-direction: column;
  background: var(--color-bg-hard);
  color: var(--color-fg);
  opacity: 0;
  transition: opacity 0.2s cubic-bezier(0.15, 0.9, 0.25, 1);
}

.canvas-report--ready {
  opacity: 1;
}

/* ---- Header ---- */
.canvas-report__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 44px;
  padding: 0 16px;
  background: var(--color-bg);
  border-bottom: 1px solid var(--color-bg2);
  flex-shrink: 0;
}

.canvas-report__header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.canvas-report__header-right {
  display: flex;
  align-items: center;
}

.canvas-report__back {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  font-size: 12px;
  font-weight: 500;
  color: var(--color-fg-muted);
  background: var(--color-bg1);
  border: none;
  border-radius: 2px;
  cursor: pointer;
  transition: all 0.12s cubic-bezier(0.15, 0.9, 0.25, 1);
}

.canvas-report__back:hover {
  background: var(--color-bg2);
  color: var(--color-fg);
}

.canvas-report__back:focus-visible {
  outline: 1px solid var(--color-aqua);
  outline-offset: 1px;
}

.canvas-report__divider {
  width: 1px;
  height: 16px;
  background: var(--color-bg3);
}

.canvas-report__step-label {
  font-size: 12px;
  color: var(--color-fg-dim);
}

.canvas-report__step-name {
  font-size: 13px;
  font-weight: 600;
  font-family: var(--font-mono);
  color: var(--color-fg);
}

.canvas-report__duration {
  font-size: 12px;
  font-family: var(--font-mono);
  color: var(--color-fg-muted);
}

.canvas-report__hint {
  font-size: 11px;
  color: var(--color-fg-dim);
  padding: 2px 8px;
  background: var(--color-bg1);
  border-radius: 2px;
}

/* ---- Tabs ---- */
.canvas-report__tabs {
  display: flex;
  align-items: center;
  gap: 0;
  padding: 0 24px;
  background: var(--color-bg);
  border-bottom: 1px solid var(--color-bg2);
  flex-shrink: 0;
}

.canvas-report__tab {
  padding: 8px 16px;
  font-size: 13px;
  font-weight: 400;
  color: var(--color-fg-muted);
  background: transparent;
  border: none;
  border-bottom: 2px solid transparent;
  cursor: pointer;
  transition: all 0.12s cubic-bezier(0.15, 0.9, 0.25, 1);
}

.canvas-report__tab:hover {
  color: var(--color-fg);
}

.canvas-report__tab--active {
  color: var(--color-fg);
  font-weight: 500;
  border-bottom-color: var(--color-aqua);
}

.canvas-report__canvas-label {
  padding: 6px 24px;
  font-size: 12px;
  font-weight: 500;
  color: var(--color-fg-muted);
  background: var(--color-bg);
  border-bottom: 1px solid var(--color-bg2);
  flex-shrink: 0;
  letter-spacing: 0.02em;
  text-transform: uppercase;
}

/* ---- Body ---- */
.canvas-report__body {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
}

.canvas-report__widgets {
  max-width: 1200px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* ---- Widget variants ---- */
.canvas-report__widget {
  width: 100%;
}

.canvas-report__widget--chart {
  min-height: 500px;
}

.canvas-report__widget--chart :deep(.w-full) {
  min-height: 500px;
  height: 560px;
}

.canvas-report__widget--metrics :deep(.flex) {
  gap: 10px;
}

.canvas-report__widget--metrics :deep(.flex > div) {
  padding: 10px 16px;
}

.canvas-report__widget--metrics :deep(.text-xs) {
  font-size: 13px;
}

.canvas-report__widget--metrics :deep(.text-sm) {
  font-size: 18px;
}

.canvas-report__widget--text :deep(div) {
  padding: 16px 20px;
  font-size: 15px;
  line-height: 1.7;
}

.canvas-report__widget--image :deep(img) {
  max-width: 100%;
  max-height: 700px;
}

.canvas-report__widget-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 48px;
  font-size: 14px;
  color: var(--color-fg-dim);
}

/* ---- States ---- */
.canvas-report__loading {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  font-size: 14px;
  color: var(--color-fg-dim);
}

.canvas-report__error {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  font-size: 14px;
  color: var(--color-red);
}

.canvas-report__retry {
  padding: 6px 16px;
  font-size: 12px;
  font-weight: 500;
  color: var(--color-fg);
  background: var(--color-bg2);
  border: none;
  border-radius: 2px;
  cursor: pointer;
  transition: background 0.12s;
}

.canvas-report__retry:hover {
  background: var(--color-bg3);
}

.canvas-report__empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  font-size: 14px;
  color: var(--color-fg-dim);
}

.canvas-report__back-link {
  padding: 4px 12px;
  font-size: 12px;
  color: var(--color-aqua);
  background: var(--color-bg1);
  border: none;
  border-radius: 2px;
  cursor: pointer;
  transition: background 0.12s;
}

.canvas-report__back-link:hover {
  background: var(--color-bg2);
}
</style>
