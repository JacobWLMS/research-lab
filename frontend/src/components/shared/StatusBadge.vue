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
    case 'completed': return 'var(--c-green)'
    case 'running': return 'var(--c-yellow)'
    case 'failed': return 'var(--c-red)'
    default: return 'var(--c-fg-dim)'
  }
})
</script>

<template>
  <span class="status-badge">
    <span
      class="status-badge__dot"
      :class="{ 'animate-pulse-glow': status === 'running' }"
      :style="{ background: color }"
    />
    <span
      v-if="showLabel"
      class="status-badge__label"
      :style="{ color }"
    >{{ status }}</span>
  </span>
</template>

<style scoped>
.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.375rem;
  flex-shrink: 0;
}

.status-badge__dot {
  display: inline-block;
  width: 0.5rem;
  height: 0.5rem;
  border-radius: 50%;
  flex-shrink: 0;
  transition: background 0.2s;
}

.status-badge__label {
  font-size: 0.75rem;
  text-transform: capitalize;
  transition: color 0.2s;
}
</style>
