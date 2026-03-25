<script setup lang="ts">
defineProps<{
  content: string
}>()
</script>

<template>
  <div class="text-block">{{ content }}</div>
</template>

<style scoped>
.text-block {
  padding: 0.625rem 0.75rem;
  border-left: 2px solid var(--c-aqua);
  background: var(--c-bg1);
  color: var(--c-fg2);
  font-size: 0.875rem;
  line-height: 1.6;
  white-space: pre-wrap;
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
}
</style>
