<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useNotifications } from '../../composables/useNotifications'

const { notifications, unreadCount, markAsRead, markAllAsRead, dismiss } = useNotifications()
const router = useRouter()

// Relative time
const now = ref(Date.now())
let timer: ReturnType<typeof setInterval> | null = null

onMounted(() => {
  timer = setInterval(() => { now.value = Date.now() }, 15_000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})

function relativeTime(ts: number): string {
  const diff = now.value - ts
  if (diff < 10_000) return 'just now'
  const sec = Math.floor(diff / 1000)
  if (sec < 60) return `${sec}s ago`
  const min = Math.floor(sec / 60)
  if (min < 60) return `${min}m ago`
  const hr = Math.floor(min / 60)
  if (hr < 24) return `${hr}h ago`
  return `${Math.floor(hr / 24)}d ago`
}

function eventIcon(type: string): string {
  if (type === 'step_completed') return 'completed'
  if (type === 'pipeline_completed') return 'pipeline'
  if (type === 'canvas_update') return 'canvas'
  return 'default'
}

function eventColor(type: string): string {
  if (type === 'step_completed') return 'var(--c-green)'
  if (type === 'pipeline_completed') return 'var(--c-green)'
  if (type === 'canvas_update') return 'var(--c-purple)'
  if (type === 'experiment_created') return 'var(--c-aqua)'
  return 'var(--c-fg-dim)'
}

function navigateToNotification(n: { id: number; experimentId: string; stepName: string }) {
  markAsRead(n.id)
  if (n.experimentId) {
    router.push({ name: 'experiment', params: { id: n.experimentId } })
  }
}
</script>

<template>
  <div class="notif-panel">
    <div class="notif-panel__header">
      <span class="notif-panel__title">Notifications</span>
      <button
        v-if="unreadCount > 0"
        class="notif-panel__mark-all"
        @click="markAllAsRead"
      >Mark all read</button>
    </div>

    <div v-if="notifications.length === 0" class="notif-panel__empty">
      No notifications yet
    </div>

    <div v-else class="notif-panel__list">
      <div
        v-for="n in notifications"
        :key="n.id"
        class="notif-panel__item"
        :class="{ 'notif-panel__item--unread': !n.read }"
        @click="navigateToNotification(n)"
      >
        <span
          class="notif-panel__dot"
          :style="{ background: eventColor(n.type) }"
        />
        <div class="notif-panel__content">
          <span class="notif-panel__message">{{ n.message }}</span>
          <span class="notif-panel__time">{{ relativeTime(n.timestamp) }}</span>
        </div>
        <button
          class="notif-panel__dismiss"
          title="Dismiss"
          @click.stop="dismiss(n.id)"
        >
          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M18 6L6 18M6 6l12 12" stroke-linecap="round"/>
          </svg>
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.notif-panel {
  position: absolute;
  top: 100%;
  right: 0;
  margin-top: 0.25rem;
  width: 20rem;
  max-height: 24rem;
  background: var(--c-bg);
  border: 1px solid var(--c-border);
  border-radius: var(--radius-md);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);
  z-index: 200;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  animation: slide-up 0.1s ease;
}

.notif-panel__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.5rem 0.75rem;
  border-bottom: 1px solid var(--c-border-subtle);
  flex-shrink: 0;
}

.notif-panel__title {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--c-fg-muted);
}

.notif-panel__mark-all {
  font-size: 0.625rem;
  color: var(--c-aqua);
  background: transparent;
  border: none;
  cursor: pointer;
  padding: 0.125rem 0.25rem;
  border-radius: var(--radius-sm);
  transition: background 0.08s;
}

.notif-panel__mark-all:hover {
  background: var(--c-surface-hover);
}

.notif-panel__empty {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 2rem 1rem;
  font-size: 0.75rem;
  color: var(--c-fg-dim);
}

.notif-panel__list {
  overflow-y: auto;
  flex: 1;
}

.notif-panel__item {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
  padding: 0.5rem 0.75rem;
  cursor: pointer;
  transition: background 0.08s;
}

.notif-panel__item:hover {
  background: var(--c-surface-hover);
}

.notif-panel__item--unread {
  background: color-mix(in srgb, var(--c-aqua) 5%, transparent);
}

.notif-panel__item--unread:hover {
  background: color-mix(in srgb, var(--c-aqua) 10%, transparent);
}

.notif-panel__dot {
  width: 0.375rem;
  height: 0.375rem;
  border-radius: 50%;
  flex-shrink: 0;
  margin-top: 0.3125rem;
}

.notif-panel__content {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.125rem;
}

.notif-panel__message {
  font-size: 0.6875rem;
  color: var(--c-fg);
  line-height: 1.3;
}

.notif-panel__time {
  font-size: 0.5625rem;
  color: var(--c-fg-dim);
}

.notif-panel__dismiss {
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
  flex-shrink: 0;
  opacity: 0;
  transition: opacity 0.08s, color 0.08s;
}

.notif-panel__item:hover .notif-panel__dismiss {
  opacity: 1;
}

.notif-panel__dismiss:hover {
  color: var(--c-fg);
  background: var(--c-surface-active);
}
</style>
