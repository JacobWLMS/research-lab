<script setup lang="ts">
import type { Step, StepResult } from '../../types'

defineProps<{
  steps: Step[]
  results: Record<string, StepResult>
}>()

const emit = defineEmits<{
  clickStep: [name: string]
}>()

function statusColor(status: string): string {
  switch (status) {
    case 'completed': return 'var(--color-green)'
    case 'running': return 'var(--color-yellow)'
    case 'failed': return 'var(--color-red)'
    default: return 'var(--color-fg-dim)'
  }
}

function fmtDur(s: number | undefined): string {
  if (!s) return ''
  if (s < 1) return `${(s * 1000).toFixed(0)}ms`
  if (s < 60) return `${s.toFixed(1)}s`
  const m = Math.floor(s / 60)
  const sec = Math.floor(s % 60)
  return `${m}m ${sec}s`
}
</script>

<template>
  <div class="flex items-center gap-0 px-4 py-2.5 overflow-x-auto">
    <template v-for="(step, i) in steps" :key="step.name">
      <!-- Connector line -->
      <div
        v-if="i > 0"
        class="w-6 shrink-0"
        style="height: 1px"
        :style="{ background: statusColor(steps[i - 1].status) }"
      />

      <!-- Step node -->
      <button
        class="flex items-center gap-1.5 px-3 py-1 shrink-0 cursor-pointer border"
        style="
          background: var(--color-bg1);
          border-color: var(--color-bg2);
          border-radius: 2px;
          transition: border-color 0.12s cubic-bezier(0.15, 0.9, 0.25, 1);
        "
        @click="emit('clickStep', step.name)"
        @mouseenter="($event.currentTarget as HTMLElement).style.borderColor = statusColor(step.status)"
        @mouseleave="($event.currentTarget as HTMLElement).style.borderColor = 'var(--color-bg2)'"
      >
        <!-- Status dot -->
        <span
          class="w-2 h-2 rounded-full shrink-0"
          :class="{ 'animate-pulse-glow': step.status === 'running' }"
          :style="{ background: statusColor(step.status) }"
        />
        <!-- Name + duration -->
        <div class="flex flex-col items-start">
          <span class="text-xs font-medium whitespace-nowrap" style="color: var(--color-fg)">
            {{ step.name }}
          </span>
          <span
            v-if="results[step.name]"
            class="text-[10px] font-mono leading-tight"
            style="color: var(--color-fg-dim)"
          >{{ fmtDur(results[step.name].execution_time_s) }}</span>
        </div>
      </button>
    </template>

    <span v-if="steps.length === 0" class="text-xs" style="color: var(--color-fg-dim)">
      No steps defined
    </span>
  </div>
</template>
