<script setup lang="ts">
defineProps<{
  content: string
}>()
</script>

<template>
  <div
    class="px-3 py-2.5 border-l-2 col-span-full text-sm leading-relaxed whitespace-pre-wrap"
    style="
      background: var(--color-bg1);
      border-left-color: var(--color-aqua);
      color: var(--color-fg2);
      border-radius: 0 2px 2px 0;
    "
  >{{ content }}</div>
</template>
