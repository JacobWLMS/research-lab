<script setup lang="ts">
import { computed } from 'vue'
import type { StepStatus } from '../../types'

const props = withDefaults(defineProps<{
  status: StepStatus | string
  showLabel?: boolean
}>(), {
  showLabel: true,
})

const color = computed(() => {
  switch (props.status) {
    case 'completed': return 'var(--color-green)'
    case 'running': return 'var(--color-yellow)'
    case 'failed': return 'var(--color-red)'
    default: return 'var(--color-fg-dim)'
  }
})
</script>

<template>
  <span class="inline-flex items-center gap-1.5 shrink-0">
    <span
      class="inline-block w-2 h-2 rounded-full shrink-0"
      :class="{ 'animate-pulse-glow': status === 'running' }"
      :style="{ background: color }"
    />
    <span
      v-if="showLabel"
      class="text-xs capitalize"
      :style="{ color }"
    >{{ status }}</span>
  </span>
</template>
