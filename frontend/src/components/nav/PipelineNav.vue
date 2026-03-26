<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import type { Step, StepResult, CanvasData, StepStatus } from '../../types'

const props = defineProps<{
  steps: Step[]
  results: Record<string, StepResult>
  canvases?: Record<string, CanvasData[]>
  activeStep?: string
}>()

const emit = defineEmits<{
  clickStep: [name: string]
  clickDashboard: []
  openAssets: []
}>()

// Asset count
const assetCount = ref(0)

async function fetchAssetCount() {
  // We don't have the experiment ID here, so skip -- parent handles asset navigation
}

function statusColor(status: StepStatus): string {
  switch (status) {
    case 'completed': return 'var(--c-green)'
    case 'running': return 'var(--c-yellow)'
    case 'failed': return 'var(--c-red)'
    default: return 'var(--c-fg-dim)'
  }
}

function connectorColor(index: number): string {
  // Color based on the preceding step's status
  if (index <= 0) return 'var(--c-fg-dim)'
  const prevStep = props.steps[index - 1]
  return statusColor(prevStep.status)
}

function formatDuration(seconds: number | undefined): string {
  if (seconds == null || seconds < 0) return ''
  if (seconds < 60) return `${Math.round(seconds)}s`
  const min = Math.floor(seconds / 60)
  const sec = Math.round(seconds % 60)
  return sec > 0 ? `${min}m ${sec}s` : `${min}m`
}

function getPreviewImage(stepName: string): string | null {
  // Find first image widget from canvases
  const stepCanvases = props.canvases?.[stepName] || []
  for (const canvas of stepCanvases) {
    for (const widget of canvas.widgets || []) {
      if (widget.kind === 'image' && 'data' in widget && (widget as any).data) {
        const data = (widget as any).data as string
        if (data.length > 100 && !data.startsWith('[')) {
          return `data:${(widget as any).mime || 'image/png'};base64,${data}`
        }
      }
    }
  }
  // Check step result images
  const result = props.results[stepName]
  if (result?.images?.length) {
    const img = result.images[0]
    if (img.data && img.data.length > 100 && !img.data.startsWith('[')) {
      return `data:${img.mime || 'image/png'};base64,${img.data}`
    }
  }
  return null
}

function progressPct(stepName: string): number | null {
  // Not directly available here -- parent can pass progress
  return null
}
</script>

<template>
  <div class="pipeline-nav">
    <!-- Dashboard link -->
    <button
      class="pipeline-nav__dashboard"
      :class="{ 'pipeline-nav__dashboard--active': !activeStep }"
      @click="emit('clickDashboard')"
    >
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <rect x="3" y="3" width="7" height="7" rx="1"/>
        <rect x="14" y="3" width="7" height="7" rx="1"/>
        <rect x="3" y="14" width="7" height="7" rx="1"/>
        <rect x="14" y="14" width="7" height="7" rx="1"/>
      </svg>
      <span>Dashboard</span>
    </button>

    <!-- Pipeline label -->
    <div class="pipeline-nav__label">PIPELINE</div>

    <!-- Steps -->
    <div class="pipeline-nav__steps">
      <template v-for="(step, i) in steps" :key="step.name">
        <!-- Connector line -->
        <div v-if="i > 0" class="pipeline-nav__connector">
          <div class="pipeline-nav__connector-line" :style="{ background: connectorColor(i) }" />
        </div>

        <!-- Step row -->
        <button
          class="pipeline-nav__step"
          :class="{
            'pipeline-nav__step--active': activeStep === step.name,
            'pipeline-nav__step--running': step.status === 'running',
            'pipeline-nav__step--completed': step.status === 'completed',
            'pipeline-nav__step--failed': step.status === 'failed',
          }"
          @click="emit('clickStep', step.name)"
        >
          <!-- Status dot -->
          <span
            class="pipeline-nav__dot"
            :class="{ 'animate-pulse-glow': step.status === 'running' }"
            :style="{ background: statusColor(step.status) }"
          />

          <!-- Step info -->
          <div class="pipeline-nav__step-info">
            <div class="pipeline-nav__step-row">
              <span class="pipeline-nav__step-title">{{ step.title || step.name }}</span>
              <span
                v-if="results[step.name]"
                class="pipeline-nav__step-duration"
              >{{ formatDuration(results[step.name].execution_time_s) }}</span>
            </div>
            <span
              v-if="step.title && step.title !== step.name"
              class="pipeline-nav__step-id"
            >{{ step.name }}</span>
          </div>

          <!-- Preview thumbnail -->
          <img
            v-if="getPreviewImage(step.name)"
            :src="getPreviewImage(step.name)!"
            class="pipeline-nav__preview"
            alt="preview"
          />
        </button>
      </template>

      <!-- Empty state -->
      <div v-if="steps.length === 0" class="pipeline-nav__empty">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="color: var(--c-fg-dim)">
          <path d="M12 5v14m-7-7h14" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        <span>No steps</span>
      </div>
    </div>

    <!-- Assets link -->
    <button class="pipeline-nav__assets" @click="emit('openAssets')">
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
        <rect x="3" y="3" width="7" height="7" rx="1"/>
        <rect x="14" y="3" width="7" height="7" rx="1"/>
        <rect x="3" y="14" width="7" height="7" rx="1"/>
        <rect x="14" y="14" width="7" height="7" rx="1"/>
      </svg>
      <span>Assets</span>
    </button>
  </div>
</template>

<style scoped>
.pipeline-nav {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 0;
}

.pipeline-nav__dashboard {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  padding: 0.5rem 0.625rem;
  font-size: var(--mc-label-size);
  font-weight: 500;
  color: var(--c-fg-muted);
  background: transparent;
  border: none;
  cursor: pointer;
  transition: background 0.08s, color 0.08s;
  border-bottom: 1px solid var(--c-border-subtle);
  text-align: left;
}

.pipeline-nav__dashboard:hover {
  background: var(--c-surface-hover);
  color: var(--c-fg);
}

.pipeline-nav__dashboard--active {
  background: var(--c-surface-hover);
  color: var(--c-aqua);
}

.pipeline-nav__label {
  padding: 0.5rem 0.625rem 0.25rem;
  font-size: 0.5625rem;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--c-fg-dim);
}

.pipeline-nav__steps {
  flex: 1;
  overflow-y: auto;
  padding: 0 0.375rem 0.5rem;
}

/* Connector */
.pipeline-nav__connector {
  display: flex;
  justify-content: flex-start;
  padding-left: 0.875rem;
  height: 0.5rem;
}

.pipeline-nav__connector-line {
  width: 1px;
  height: 100%;
  transition: background 0.2s;
}

/* Step row */
.pipeline-nav__step {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  width: 100%;
  padding: 0.3125rem 0.375rem;
  background: transparent;
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
  text-align: left;
  transition: background 0.08s;
}

.pipeline-nav__step:hover {
  background: var(--c-surface-hover);
}

.pipeline-nav__step--active {
  background: var(--c-surface-hover);
}

.pipeline-nav__step--active::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 2px;
  background: var(--c-aqua);
  border-radius: 1px;
}

/* Status dot */
.pipeline-nav__dot {
  width: 0.5rem;
  height: 0.5rem;
  border-radius: 50%;
  flex-shrink: 0;
  transition: background 0.2s;
}

/* Step info */
.pipeline-nav__step-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.0625rem;
}

.pipeline-nav__step-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.25rem;
}

.pipeline-nav__step-title {
  font-size: 0.75rem;
  font-weight: 500;
  color: var(--c-fg);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
}

.pipeline-nav__step-duration {
  font-size: 0.625rem;
  font-family: var(--font-mono);
  color: var(--c-fg-dim);
  white-space: nowrap;
  flex-shrink: 0;
}

.pipeline-nav__step-id {
  font-size: 0.5625rem;
  font-family: var(--font-mono);
  color: var(--c-fg-dim);
  opacity: 0.6;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Preview thumbnail */
.pipeline-nav__preview {
  width: 2rem;
  height: 2rem;
  object-fit: cover;
  border-radius: var(--radius-sm);
  border: 1px solid var(--c-border);
  flex-shrink: 0;
  opacity: 0.85;
  transition: opacity 0.12s;
}

.pipeline-nav__step:hover .pipeline-nav__preview {
  opacity: 1;
}

/* Empty state */
.pipeline-nav__empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.375rem;
  padding: 1.5rem 0;
  font-size: var(--mc-label-size);
  color: var(--c-fg-dim);
}

/* Assets link */
.pipeline-nav__assets {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  padding: 0.5rem 0.625rem;
  font-size: var(--mc-label-size);
  font-weight: 500;
  color: var(--c-fg-muted);
  background: transparent;
  border: none;
  border-top: 1px solid var(--c-border-subtle);
  cursor: pointer;
  transition: background 0.08s, color 0.08s;
  margin-top: auto;
  text-align: left;
}

.pipeline-nav__assets:hover {
  background: var(--c-surface-hover);
  color: var(--c-fg);
}
</style>
