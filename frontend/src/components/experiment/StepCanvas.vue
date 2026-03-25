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
    class="border overflow-hidden"
    :style="{
      background: 'var(--color-bg)',
      borderColor: isRunning ? 'var(--color-yellow)' : 'var(--color-bg2)',
      borderRadius: '2px',
      transition: 'border-color 0.12s cubic-bezier(0.15, 0.9, 0.25, 1)',
    }"
  >
    <!-- Step header bar -->
    <div
      class="flex items-center justify-between px-3 py-1.5 border-b"
      style="border-color: var(--color-bg2)"
    >
      <!-- Left: status, name, duration -->
      <div class="flex items-center gap-2">
        <StatusBadge :status="step.status" />
        <span v-if="result" class="text-xs font-mono" style="color: var(--color-fg-dim)">
          {{ fmtDur(result.execution_time_s) }}
        </span>
        <span v-if="isRunning" class="text-xs font-medium" style="color: var(--color-yellow)">
          Running...
        </span>
      </div>

      <!-- Right: disclosures + actions -->
      <div class="flex items-center gap-1">
        <button
          class="text-xs px-2 py-0.5 cursor-pointer"
          :style="{
            background: showCode ? 'var(--color-bg2)' : 'transparent',
            color: 'var(--color-fg-muted)',
            borderRadius: '2px',
            transition: 'all 0.12s',
          }"
          @click="showCode = !showCode"
        >{{ showCode ? '\u25BC' : '\u25B6' }} Code</button>
        <button
          class="text-xs px-2 py-0.5 cursor-pointer"
          :style="{
            background: showLogs ? 'var(--color-bg2)' : 'transparent',
            color: 'var(--color-fg-muted)',
            borderRadius: '2px',
            transition: 'all 0.12s',
          }"
          @click="showLogs = !showLogs"
        >{{ showLogs ? '\u25BC' : '\u25B6' }} Logs</button>
      </div>
    </div>

    <!-- Code block (collapsible) -->
    <div v-if="showCode" class="border-b" style="border-color: var(--color-bg2)">
      <CodeBlock
        :code="step.code"
        :editable="!isRunning"
        @update:code="(code: string) => emit('updateCode', code)"
      />
    </div>

    <!-- Step body -->
    <div class="p-3">
      <!-- Metrics summary chips -->
      <div
        v-if="Object.keys(summaryMetrics).length > 0"
        class="mb-2"
      >
        <MetricStrip :data="summaryMetrics" />
      </div>

      <!-- Progress bar -->
      <div v-if="progress && progress.total > 0" class="mb-2">
        <div class="flex items-center justify-between mb-0.5">
          <span class="text-xs font-mono" style="color: var(--color-fg-muted)">
            {{ progress.current }}/{{ progress.total }}
          </span>
          <span class="text-xs" style="color: var(--color-fg-dim)">{{ fmtEta(progress.eta_s) }}</span>
        </div>
        <div class="h-1 w-full overflow-hidden" style="background: var(--color-bg2); border-radius: 2px">
          <div
            class="h-full"
            :style="{
              width: progressPct + '%',
              background: step.status === 'failed' ? 'var(--color-red)' : 'var(--color-aqua)',
              transition: 'width 0.3s ease-out',
            }"
          />
        </div>
      </div>

      <!-- Streaming output (compact, only when running or has output) -->
      <div v-if="hasOutput || isRunning || !!result">
        <StreamingOutput :lines="outputLines" />
      </div>

      <!-- Empty state: not executed -->
      <div
        v-else
        class="flex flex-col items-center justify-center py-6 gap-1"
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="color: var(--color-fg-dim)">
          <circle cx="12" cy="12" r="10"/>
          <polyline points="12 6 12 12 16 14"/>
        </svg>
        <span class="text-xs" style="color: var(--color-fg-dim)">Not yet executed</span>
      </div>

      <!-- Action row -->
      <div class="mt-3 flex items-center gap-2">
        <!-- Stop button (running) -->
        <button
          v-if="isRunning"
          class="flex items-center gap-1 px-3 py-1 text-xs font-medium cursor-pointer"
          style="background: var(--color-red); color: var(--color-bg-hard); border-radius: 2px"
          @click="emit('stop')"
        >Stop</button>
        <svg
          v-if="isRunning"
          class="animate-spin h-3.5 w-3.5"
          viewBox="0 0 24 24"
          fill="none"
          style="color: var(--color-yellow)"
        >
          <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="2" opacity="0.25"/>
          <path d="M4 12a8 8 0 018-8" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
        </svg>

        <!-- Run button (not running) -->
        <button
          v-if="!isRunning"
          class="flex items-center gap-1 px-3 py-1 text-xs font-medium cursor-pointer"
          style="background: var(--color-bg2); color: var(--color-fg); border-radius: 2px; transition: background 0.12s"
          @click="emit('run')"
          @mouseenter="($event.currentTarget as HTMLElement).style.background = 'var(--color-bg3)'"
          @mouseleave="($event.currentTarget as HTMLElement).style.background = 'var(--color-bg2)'"
        >
          <svg width="10" height="10" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>
          Run Step
        </button>

        <div class="flex-1" />

        <!-- View Report button -->
        <button
          v-if="hasCanvases"
          class="step-canvas__report-btn flex items-center gap-1.5 px-3 py-1 text-xs font-medium cursor-pointer"
          @click="openCanvasReport"
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
            <path d="M3 9h18M9 21V9" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          View Report
          <span class="step-canvas__widget-count">{{ canvasWidgetCount }}</span>
        </button>
        <span
          v-else-if="step.status === 'completed' || step.status === 'failed'"
          class="text-xs"
          style="color: var(--color-fg-dim)"
        >No report</span>
      </div>
    </div>

    <!-- ========== LOGS PANEL (collapsible) ========== -->
    <div v-if="showLogs" class="border-t" style="border-color: var(--color-bg2)">
      <div class="p-3">
        <template v-if="result">
          <div class="text-xs font-medium mb-1" style="color: var(--color-fg-muted)">Full Output</div>
          <StreamingOutput :lines="result.stdout ? result.stdout.split('\n') : []" />
          <div v-if="result.stderr" class="mt-2">
            <div class="text-xs font-medium mb-1" style="color: var(--color-red)">Stderr</div>
            <StreamingOutput :lines="result.stderr.split('\n')" />
          </div>
          <div
            v-if="result.error"
            class="mt-2 p-2 text-xs font-mono"
            style="background: var(--color-bg1); color: var(--color-red); border-radius: 2px"
          >{{ result.error }}</div>
        </template>
        <div
          v-else
          class="flex items-center justify-center py-3 text-xs"
          style="color: var(--color-fg-dim)"
        >No logs available</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.step-canvas__report-btn {
  background: var(--color-aqua);
  color: var(--color-bg-hard);
  border: none;
  border-radius: 2px;
  transition: all 0.12s cubic-bezier(0.15, 0.9, 0.25, 1);
}

.step-canvas__report-btn:hover {
  filter: brightness(1.1);
}

.step-canvas__report-btn:active {
  filter: brightness(0.95);
}

.step-canvas__widget-count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 16px;
  height: 16px;
  padding: 0 4px;
  font-size: 10px;
  font-weight: 600;
  font-family: var(--font-mono);
  background: rgba(29, 32, 33, 0.25);
  border-radius: 2px;
}
</style>
