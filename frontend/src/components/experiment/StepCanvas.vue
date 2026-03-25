<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import type {
  Step,
  StepResult,
  CanvasData,
} from '../../types'
import StatusBadge from '../shared/StatusBadge.vue'
import StreamingOutput from '../shared/StreamingOutput.vue'
import CodeBlock from '../shared/CodeBlock.vue'
import MetricStrip from '../widgets/MetricStrip.vue'

const props = defineProps<{
  step: Step
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
}>()

const router = useRouter()
const route = useRoute()
const showCode = ref(false)
const showLogs = ref(false)

const isRunning = computed(() => props.step.status === 'running')

const hasCanvases = computed(() => {
  return props.canvases.length > 0 &&
    props.canvases.some((c) => c.widgets.length > 0)
})

const canvasWidgetCount = computed(() => {
  return props.canvases.reduce((sum, c) => sum + c.widgets.length, 0)
})

const progressPct = computed(() => {
  if (!props.progress || props.progress.total <= 0) return 0
  return Math.min(100, (props.progress.current / props.progress.total) * 100)
})

const hasOutput = computed(() => {
  return props.outputLines.length > 0 ||
    Object.keys(props.liveMetrics).length > 0 ||
    (props.progress && props.progress.total > 0)
})

// Combine result metrics + live metrics for the summary chips
const summaryMetrics = computed<Record<string, number | string>>(() => {
  const m: Record<string, number | string> = {}
  if (props.result && props.result.metrics) {
    Object.assign(m, props.result.metrics)
  }
  if (props.liveMetrics) {
    Object.assign(m, props.liveMetrics)
  }
  return m
})

const experimentId = computed(() => {
  return (route.params.id as string) ?? ''
})

function fmtDur(s: number | undefined): string {
  if (!s) return ''
  if (s < 1) return `${(s * 1000).toFixed(0)}ms`
  if (s < 60) return `${s.toFixed(1)}s`
  const m = Math.floor(s / 60)
  const sec = Math.floor(s % 60)
  return `${m}m ${sec}s`
}

function fmtEta(s?: number): string {
  if (!s || s <= 0) return ''
  if (s < 60) return `~${Math.ceil(s)}s`
  const m = Math.floor(s / 60)
  const sec = Math.ceil(s % 60)
  return `~${m}m ${sec}s`
}

function openCanvasReport() {
  if (!experimentId.value) return
  router.push({
    name: 'canvas-report',
    params: {
      experimentId: experimentId.value,
      stepName: props.step.name,
    },
  })
}
</script>

<template>
  <div
    class="step-card"
    :class="{
      'step-card--running': isRunning,
      'step-card--completed': step.status === 'completed',
      'step-card--failed': step.status === 'failed',
    }"
  >
    <!-- Step header bar -->
    <div class="step-card__header">
      <!-- Left: status, name, duration -->
      <div class="step-card__header-left">
        <StatusBadge :status="step.status" />
        <span v-if="result" class="step-card__duration">{{ fmtDur(result.execution_time_s) }}</span>
        <span v-if="isRunning" class="step-card__running-label">Running...</span>
      </div>

      <!-- Right: disclosures + actions -->
      <div class="step-card__header-right">
        <button
          class="step-card__toggle"
          :class="{ 'step-card__toggle--active': showCode }"
          @click="showCode = !showCode"
        >
          <svg width="8" height="8" viewBox="0 0 24 24" fill="currentColor">
            <path :d="showCode ? 'M7 10l5 5 5-5z' : 'M10 17l5-5-5-5z'"/>
          </svg>
          Code
        </button>
        <button
          class="step-card__toggle"
          :class="{ 'step-card__toggle--active': showLogs }"
          @click="showLogs = !showLogs"
        >
          <svg width="8" height="8" viewBox="0 0 24 24" fill="currentColor">
            <path :d="showLogs ? 'M7 10l5 5 5-5z' : 'M10 17l5-5-5-5z'"/>
          </svg>
          Logs
        </button>
      </div>
    </div>

    <!-- Code block (collapsible) -->
    <div v-if="showCode" class="step-card__code animate-slide-up">
      <CodeBlock
        :code="step.code"
        :editable="!isRunning"
        @update:code="(code: string) => emit('updateCode', code)"
      />
    </div>

    <!-- Step body -->
    <div class="step-card__body">
      <!-- Metrics summary chips -->
      <div v-if="Object.keys(summaryMetrics).length > 0" class="step-card__metrics">
        <MetricStrip :data="summaryMetrics" />
      </div>

      <!-- Progress bar -->
      <div v-if="progress && progress.total > 0" class="step-card__progress">
        <div class="step-card__progress-info">
          <span class="step-card__progress-count">{{ progress.current }}/{{ progress.total }}</span>
          <span class="step-card__progress-eta">{{ fmtEta(progress.eta_s) }}</span>
        </div>
        <div class="step-card__progress-bar">
          <div
            class="step-card__progress-fill"
            :style="{
              width: progressPct + '%',
              background: step.status === 'failed' ? 'var(--c-red)' : 'var(--c-aqua)',
            }"
          />
        </div>
      </div>

      <!-- Streaming output (compact, only when running or has output) -->
      <div v-if="hasOutput || isRunning || !!result">
        <StreamingOutput :lines="outputLines" />
      </div>

      <!-- Empty state: not executed -->
      <div v-else class="step-card__empty">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="color: var(--c-fg-dim)">
          <circle cx="12" cy="12" r="10"/>
          <polyline points="12 6 12 12 16 14"/>
        </svg>
        <span>Not yet executed</span>
      </div>

      <!-- Action row -->
      <div class="step-card__actions">
        <!-- Stop button (running) -->
        <button v-if="isRunning" class="step-card__stop-btn" @click="emit('stop')">Stop</button>
        <svg
          v-if="isRunning"
          class="animate-spin"
          width="14"
          height="14"
          viewBox="0 0 24 24"
          fill="none"
          style="color: var(--c-yellow)"
        >
          <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="2" opacity="0.25"/>
          <path d="M4 12a8 8 0 018-8" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
        </svg>

        <!-- Run button (not running) -->
        <button
          v-if="!isRunning"
          class="step-card__run-btn"
          title="Run this step (Ctrl+Enter)"
          @click="emit('run')"
        >
          <svg width="10" height="10" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>
          Run Step
        </button>

        <div style="flex: 1" />

        <!-- View Report button -->
        <button
          v-if="hasCanvases"
          class="step-card__report-btn"
          @click="openCanvasReport"
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
            <path d="M3 9h18M9 21V9" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          View Report
          <span class="step-card__widget-count">{{ canvasWidgetCount }}</span>
        </button>
        <span
          v-else-if="step.status === 'completed' || step.status === 'failed'"
          class="step-card__no-report"
        >No report</span>
      </div>
    </div>

    <!-- Logs panel (collapsible) -->
    <div v-if="showLogs" class="step-card__logs animate-slide-up">
      <template v-if="result">
        <div class="step-card__logs-label">Full Output</div>
        <StreamingOutput :lines="result.stdout ? result.stdout.split('\n') : []" />
        <div v-if="result.stderr" class="step-card__logs-section">
          <div class="step-card__logs-label step-card__logs-label--error">Stderr</div>
          <StreamingOutput :lines="result.stderr.split('\n')" />
        </div>
        <div v-if="result.error" class="step-card__error-box">{{ result.error }}</div>
      </template>
      <div v-else class="step-card__logs-empty">No logs available</div>
    </div>
  </div>
</template>

<style scoped>
.step-card {
  border: 1px solid var(--c-border);
  border-radius: var(--radius-md);
  background: var(--c-surface);
  overflow: hidden;
  transition: border-color 0.15s;
}

.step-card--running {
  border-color: var(--c-yellow);
}

.step-card--completed {
  border-color: var(--c-border);
}

.step-card--failed {
  border-color: var(--c-red);
}

/* Header */
.step-card__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.375rem 0.75rem;
  border-bottom: 1px solid var(--c-border-subtle);
}

.step-card__header-left {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.step-card__header-right {
  display: flex;
  align-items: center;
  gap: 0.25rem;
}

.step-card__duration {
  font-size: 0.75rem;
  font-family: var(--font-mono);
  color: var(--c-fg-dim);
}

.step-card__running-label {
  font-size: 0.75rem;
  font-weight: 500;
  color: var(--c-yellow);
}

/* Toggle buttons */
.step-card__toggle {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  font-size: 0.75rem;
  padding: 0.125rem 0.5rem;
  color: var(--c-fg-muted);
  background: transparent;
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: background 0.12s, color 0.12s;
}

.step-card__toggle:hover {
  background: var(--c-surface-hover);
}

.step-card__toggle--active {
  background: var(--c-surface-active);
  color: var(--c-fg);
}

/* Code section */
.step-card__code {
  border-bottom: 1px solid var(--c-border-subtle);
}

/* Body */
.step-card__body {
  padding: 0.75rem;
}

.step-card__metrics {
  margin-bottom: 0.5rem;
}

/* Progress */
.step-card__progress {
  margin-bottom: 0.5rem;
}

.step-card__progress-info {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.25rem;
}

.step-card__progress-count {
  font-size: 0.75rem;
  font-family: var(--font-mono);
  color: var(--c-fg-muted);
}

.step-card__progress-eta {
  font-size: 0.75rem;
  color: var(--c-fg-dim);
}

.step-card__progress-bar {
  height: 0.25rem;
  width: 100%;
  background: var(--c-bg2);
  border-radius: var(--radius-sm);
  overflow: hidden;
}

.step-card__progress-fill {
  height: 100%;
  transition: width 0.3s ease-out;
  border-radius: var(--radius-sm);
}

/* Empty state */
.step-card__empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 1.5rem 0;
  gap: 0.25rem;
  font-size: 0.75rem;
  color: var(--c-fg-dim);
}

/* Actions */
.step-card__actions {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-top: 0.75rem;
}

.step-card__stop-btn {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.25rem 0.75rem;
  font-size: 0.75rem;
  font-weight: 500;
  background: var(--c-red);
  color: var(--c-bg-hard);
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: filter 0.12s;
}

.step-card__stop-btn:hover {
  filter: brightness(1.1);
}

.step-card__run-btn {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.25rem 0.75rem;
  font-size: 0.75rem;
  font-weight: 500;
  background: var(--c-bg2);
  color: var(--c-fg);
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: background 0.12s;
}

.step-card__run-btn:hover {
  background: var(--c-bg3);
}

.step-card__report-btn {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  padding: 0.25rem 0.75rem;
  font-size: 0.75rem;
  font-weight: 500;
  background: var(--c-aqua);
  color: var(--c-bg-hard);
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: filter 0.12s;
}

.step-card__report-btn:hover {
  filter: brightness(1.1);
}

.step-card__report-btn:active {
  filter: brightness(0.95);
}

.step-card__widget-count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 1rem;
  height: 1rem;
  padding: 0 0.25rem;
  font-size: 0.625rem;
  font-weight: 600;
  font-family: var(--font-mono);
  background: rgba(0, 0, 0, 0.15);
  border-radius: var(--radius-sm);
}

.step-card__no-report {
  font-size: 0.75rem;
  color: var(--c-fg-dim);
}

/* Logs panel */
.step-card__logs {
  border-top: 1px solid var(--c-border-subtle);
  padding: 0.75rem;
}

.step-card__logs-label {
  font-size: 0.75rem;
  font-weight: 500;
  color: var(--c-fg-muted);
  margin-bottom: 0.25rem;
}

.step-card__logs-label--error {
  color: var(--c-red);
}

.step-card__logs-section {
  margin-top: 0.5rem;
}

.step-card__error-box {
  margin-top: 0.5rem;
  padding: 0.5rem;
  font-size: 0.75rem;
  font-family: var(--font-mono);
  background: var(--c-bg1);
  color: var(--c-red);
  border-radius: var(--radius-sm);
}

.step-card__logs-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0.75rem;
  font-size: 0.75rem;
  color: var(--c-fg-dim);
}
</style>
