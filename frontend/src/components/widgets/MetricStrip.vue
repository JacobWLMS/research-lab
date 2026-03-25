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
  <div class="flex flex-wrap gap-1.5 col-span-full">
    <div
      v-for="(value, key) in data"
      :key="key"
      class="flex items-center gap-2 px-2.5 py-1.5"
      style="background: var(--color-bg1); border-radius: 2px"
    >
      <span class="text-xs" style="color: var(--color-fg-muted)">{{ key }}</span>
      <span class="text-sm font-mono font-medium" style="color: var(--color-fg)">{{ fmt(value) }}</span>
    </div>
  </div>
</template>
