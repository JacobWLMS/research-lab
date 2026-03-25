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
    <div v-if="title" class="image-widget__title">{{ title }}</div>
    <img
      :src="src"
      :alt="title ?? 'Image output'"
      class="image-widget__img"
      @click="showOverlay = true"
    />
    <!-- Lightbox overlay -->
    <Teleport to="body">
      <div
        v-if="showOverlay"
        class="image-widget__overlay animate-fade-in"
        @click="showOverlay = false"
      >
        <img
          :src="src"
          :alt="title ?? 'Image output'"
          class="image-widget__overlay-img"
        />
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.image-widget__title {
  font-size: 0.75rem;
  font-weight: 500;
  color: var(--c-fg-muted);
  margin-bottom: 0.25rem;
}

.image-widget__img {
  max-width: 100%;
  cursor: pointer;
  border: 1px solid var(--c-border);
  border-radius: var(--radius-sm);
  transition: opacity 0.12s;
}

.image-widget__img:hover {
  opacity: 0.85;
}

.image-widget__overlay {
  position: fixed;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 200;
  background: var(--c-overlay);
  cursor: pointer;
}

.image-widget__overlay-img {
  max-width: 90vw;
  max-height: 90vh;
  border: 1px solid var(--c-border);
  border-radius: var(--radius-sm);
}
</style>
