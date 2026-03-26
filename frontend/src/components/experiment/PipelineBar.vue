<script setup lang="ts">
import type { Step, StepResult } from '../../types'

import type { CanvasData } from '../../types'

const props = defineProps<{
  steps: Step[]
  results: Record<string, StepResult>
  canvases?: Record<string, CanvasData[]>
}>()

const emit = defineEmits<{
  clickStep: [name: string]
}>()

function statusColor(status: string): string {
  switch (status) {
    case 'completed': return 'var(--c-green)'
    case 'running': return 'var(--c-yellow)'
    case 'failed': return 'var(--c-red)'
    default: return 'var(--c-fg-dim)'
  }
}

function formatDuration(seconds: number | undefined): string {
  if (seconds == null || seconds < 0) return ''
  if (seconds < 60) return `${Math.round(seconds)}s`
  const min = Math.floor(seconds / 60)
  const sec = Math.round(seconds % 60)
  return sec > 0 ? `${min}m ${sec}s` : `${min}m`
}

function statusLabel(status: string): string {
  return status.charAt(0).toUpperCase() + status.slice(1)
}

function getPreviewImage(stepName: string): string | null {
  // Find first image widget from canvases, or first image from step result
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
</script>

<template>
  <div class="pipeline-bar">
    <template v-for="(step, i) in steps" :key="step.name">
      <!-- Connector line -->
      <div
        v-if="i > 0"
        class="pipeline-bar__connector"
        :style="{ background: statusColor(steps[i - 1].status) }"
      />

      <!-- Step node -->
      <button
        class="pipeline-bar__node"
        :title="`${step.name} - ${statusLabel(step.status)}${results[step.name] ? ' (' + formatDuration(results[step.name].execution_time_s) + ')' : ''}`"
        @click="emit('clickStep', step.name)"
      >
        <!-- Status dot -->
        <span
          class="pipeline-bar__dot"
          :class="{ 'animate-pulse-glow': step.status === 'running' }"
          :style="{ background: statusColor(step.status) }"
        />
        <!-- Name + duration -->
        <div class="pipeline-bar__label">
          <span class="pipeline-bar__name">{{ step.title || step.name }}</span>
          <span
            v-if="results[step.name]"
            class="pipeline-bar__duration"
          >{{ formatDuration(results[step.name].execution_time_s) }}</span>
        </div>
        <!-- Preview image (first from canvas/result, max 1) -->
        <img
          v-if="getPreviewImage(step.name)"
          :src="getPreviewImage(step.name)!"
          class="pipeline-bar__preview"
          alt="preview"
        />
      </button>
    </template>

    <span v-if="steps.length === 0" class="pipeline-bar__empty">
      No steps defined
    </span>
  </div>
</template>

<style scoped>
.pipeline-bar {
  display: flex;
  align-items: center;
  padding: 0.625rem 1rem;
  overflow-x: auto;
  gap: 0;
}

.pipeline-bar__connector {
  width: 1.5rem;
  height: 1px;
  flex-shrink: 0;
  transition: background 0.2s;
}

.pipeline-bar__node {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  padding: 0.25rem 0.75rem;
  flex-shrink: 0;
  background: var(--c-bg1);
  border: 1px solid var(--c-border);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: border-color 0.12s, background 0.12s;
}

.pipeline-bar__node:hover {
  border-color: var(--c-fg-dim);
  background: var(--c-surface-hover);
}

.pipeline-bar__dot {
  width: 0.5rem;
  height: 0.5rem;
  border-radius: 50%;
  flex-shrink: 0;
  transition: background 0.2s;
}

.pipeline-bar__label {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
}

.pipeline-bar__name {
  font-size: 0.75rem;
  font-weight: 500;
  color: var(--c-fg);
  white-space: nowrap;
}

.pipeline-bar__duration {
  font-size: 0.625rem;
  font-family: var(--font-mono);
  color: var(--c-fg-dim);
  line-height: 1.2;
}

.pipeline-bar__preview {
  width: 2rem;
  height: 2rem;
  object-fit: cover;
  border-radius: var(--radius-sm);
  border: 1px solid var(--c-border);
  flex-shrink: 0;
  opacity: 0.9;
  transition: opacity 0.12s;
}

.pipeline-bar__node:hover .pipeline-bar__preview {
  opacity: 1;
}

.pipeline-bar__empty {
  font-size: 0.75rem;
  color: var(--c-fg-dim);
}
</style>
