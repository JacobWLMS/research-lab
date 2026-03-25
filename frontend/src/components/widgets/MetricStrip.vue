<script setup lang="ts">
defineProps<{
  data: Record<string, number | string>
}>()

function fmt(v: number | string): string {
  if (typeof v === 'number') {
    if (Number.isInteger(v)) return v.toString()
    return v.toFixed(4).replace(/0+$/, '').replace(/\.$/, '')
  }
  return v
}
</script>

<template>
  <div class="metric-strip">
    <div
      v-for="(value, key) in data"
      :key="key"
      class="metric-strip__chip"
    >
      <span class="metric-strip__key">{{ key }}</span>
      <span class="metric-strip__value">{{ fmt(value) }}</span>
    </div>
  </div>
</template>

<style scoped>
.metric-strip {
  display: flex;
  flex-wrap: wrap;
  gap: 0.375rem;
}

.metric-strip__chip {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.375rem 0.625rem;
  background: var(--c-bg1);
  border-radius: var(--radius-sm);
  transition: background 0.12s;
}

.metric-strip__chip:hover {
  background: var(--c-surface-hover);
}

.metric-strip__key {
  font-size: 0.75rem;
  color: var(--c-fg-muted);
}

.metric-strip__value {
  font-size: 0.875rem;
  font-family: var(--font-mono);
  font-weight: 500;
  color: var(--c-fg);
}
</style>
