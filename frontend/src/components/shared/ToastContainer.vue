<script setup lang="ts">
import { useToast } from '../../composables/useToast'

const { toasts, removeToast } = useToast()

function typeColor(type: string): string {
  switch (type) {
    case 'success': return 'var(--c-green)'
    case 'error': return 'var(--c-red)'
    default: return 'var(--c-fg-muted)'
  }
}

function typeIcon(type: string): string {
  switch (type) {
    case 'success': return 'M20 6L9 17l-5-5'
    case 'error': return 'M18 6L6 18M6 6l12 12'
    default: return 'M12 8v4m0 4h.01'
  }
}
</script>

<template>
  <Teleport to="body">
    <div class="toast-stack">
      <TransitionGroup name="toast">
        <div
          v-for="toast in toasts"
          :key="toast.id"
          class="toast-item"
          @click="removeToast(toast.id)"
        >
          <span class="toast-item__accent" :style="{ background: typeColor(toast.type) }" />
          <svg
            class="toast-item__icon"
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            :style="{ color: typeColor(toast.type) }"
          >
            <path :d="typeIcon(toast.type)" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          <span class="toast-item__text">{{ toast.message }}</span>
          <button class="toast-item__close" @click.stop="removeToast(toast.id)">
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M18 6L6 18M6 6l12 12" stroke-linecap="round"/>
            </svg>
          </button>
        </div>
      </TransitionGroup>
    </div>
  </Teleport>
</template>

<style scoped>
.toast-stack {
  position: fixed;
  bottom: 1rem;
  right: 1rem;
  z-index: 9999;
  display: flex;
  flex-direction: column-reverse;
  gap: 0.5rem;
  max-width: 22rem;
  pointer-events: none;
}

.toast-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 0.75rem;
  background: var(--c-bg);
  border: 1px solid var(--c-border);
  border-radius: var(--radius-md);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25);
  font-size: 0.8125rem;
  color: var(--c-fg);
  cursor: pointer;
  pointer-events: auto;
  overflow: hidden;
  position: relative;
}

.toast-item__accent {
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 3px;
  border-radius: var(--radius-md) 0 0 var(--radius-md);
}

.toast-item__icon {
  flex-shrink: 0;
  margin-left: 0.25rem;
}

.toast-item__text {
  flex: 1;
  min-width: 0;
  line-height: 1.4;
}

.toast-item__close {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 1.25rem;
  height: 1.25rem;
  color: var(--c-fg-dim);
  background: transparent;
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: background 0.12s, color 0.12s;
}

.toast-item__close:hover {
  background: var(--c-bg1);
  color: var(--c-fg);
}

/* Transitions */
.toast-enter-active {
  animation: slide-in-right 0.2s cubic-bezier(0.15, 0.9, 0.25, 1);
}

.toast-leave-active {
  animation: slide-out-right 0.15s cubic-bezier(0.15, 0.9, 0.25, 1) forwards;
}

.toast-move {
  transition: transform 0.2s cubic-bezier(0.15, 0.9, 0.25, 1);
}
</style>
