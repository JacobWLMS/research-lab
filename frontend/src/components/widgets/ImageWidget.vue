<script setup lang="ts">
import { ref, computed } from 'vue'

const props = defineProps<{
  title?: string
  mime: string
  data: string
}>()

const showOverlay = ref(false)
const src = computed(() => `data:${props.mime};base64,${props.data}`)
</script>

<template>
  <div>
    <div v-if="title" class="text-xs font-medium mb-1" style="color: var(--color-fg-muted)">
      {{ title }}
    </div>
    <img
      :src="src"
      :alt="title ?? 'Image output'"
      class="max-w-full cursor-pointer"
      style="border: 1px solid var(--color-bg2); border-radius: 2px; transition: opacity 0.12s"
      @click="showOverlay = true"
      @mouseenter="($event.currentTarget as HTMLElement).style.opacity = '0.85'"
      @mouseleave="($event.currentTarget as HTMLElement).style.opacity = '1'"
    />
    <!-- Lightbox overlay -->
    <Teleport to="body">
      <div
        v-if="showOverlay"
        class="fixed inset-0 flex items-center justify-center z-50 cursor-pointer animate-fade-in"
        style="background: rgba(29, 32, 33, 0.92)"
        @click="showOverlay = false"
      >
        <img
          :src="src"
          :alt="title ?? 'Image output'"
          class="max-w-[90vw] max-h-[90vh]"
          style="border: 1px solid var(--color-bg2); border-radius: 2px"
        />
      </div>
    </Teleport>
  </div>
</template>
