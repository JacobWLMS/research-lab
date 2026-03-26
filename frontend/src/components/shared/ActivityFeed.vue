<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useActivityFeed, type ActivityEntry } from '../../composables/useActivityFeed'

const { feed } = useActivityFeed()
const router = useRouter()

// Update relative timestamps every 15 seconds
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

function eventColor(type: string): string {
  if (type === 'step_completed') return 'var(--c-green)'
  if (type === 'step_started' || type === 'step_updated' || type === 'step_added') return 'var(--c-yellow)'
  if (type.includes('failed') || type === 'step_deleted' || type === 'experiment_deleted') return 'var(--c-red)'
  if (type === 'pipeline_completed') return 'var(--c-green)'
  if (type === 'experiment_created' || type === 'experiment_updated') return 'var(--c-aqua)'
  if (type === 'canvas_update') return 'var(--c-purple)'
  return 'var(--c-fg-dim)'
}

function navigateToEvent(entry: ActivityEntry) {
  if (entry.experimentId) {
    router.push({ name: 'experiment', params: { id: entry.experimentId } })
  }
}
</script>

<template>
  <div class="activity-feed">
    <div class="activity-feed__header">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
      <span>Activity Feed</span>
    </div>

    <div v-if="feed.length === 0" class="activity-feed__empty">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="color: var(--c-fg-dim)">
        <circle cx="12" cy="12" r="10"/>
        <polyline points="12 6 12 12 16 14"/>
      </svg>
      <span>No activity yet</span>
      <span class="activity-feed__empty-hint">Events will appear here as experiments run</span>
    </div>

    <div v-else class="activity-feed__list">
      <div
        v-for="entry in feed"
        :key="entry.id"
        class="activity-feed__item"
        :class="{ 'activity-feed__item--clickable': !!entry.experimentId }"
        @click="navigateToEvent(entry)"
      >
        <span
          class="activity-feed__dot"
          :style="{ background: eventColor(entry.type) }"
        />
        <div class="activity-feed__content">
          <span class="activity-feed__message">{{ entry.message }}</span>
          <span v-if="entry.experimentName" class="activity-feed__exp-name">{{ entry.experimentName }}</span>
        </div>
        <span class="activity-feed__time">{{ relativeTime(entry.timestamp) }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.activity-feed {
  display: flex;
  flex-direction: column;
  height: 100%;
  max-height: 100%;
}

.activity-feed__header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem 1rem;
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--c-fg-muted);
  border-bottom: 1px solid var(--c-border-subtle);
  flex-shrink: 0;
}

.activity-feed__empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 3rem 1rem;
  gap: 0.5rem;
  font-size: 0.8125rem;
  color: var(--c-fg-dim);
}

.activity-feed__empty-hint {
  font-size: 0.75rem;
  color: var(--c-fg-dim);
  opacity: 0.7;
}

.activity-feed__list {
  flex: 1;
  overflow-y: auto;
  padding: 0.25rem 0;
}

.activity-feed__item {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
  padding: 0.5rem 1rem;
  transition: background 0.08s;
}

.activity-feed__item--clickable {
  cursor: pointer;
}

.activity-feed__item--clickable:hover {
  background: var(--c-surface-hover);
}

.activity-feed__dot {
  width: 0.4375rem;
  height: 0.4375rem;
  border-radius: 50%;
  flex-shrink: 0;
  margin-top: 0.3125rem;
}

.activity-feed__content {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.125rem;
}

.activity-feed__message {
  font-size: 0.75rem;
  color: var(--c-fg);
  line-height: 1.3;
}

.activity-feed__exp-name {
  font-size: 0.6875rem;
  color: var(--c-fg-dim);
  font-family: var(--font-mono);
}

.activity-feed__time {
  font-size: 0.625rem;
  color: var(--c-fg-dim);
  white-space: nowrap;
  flex-shrink: 0;
  margin-top: 0.125rem;
}
</style>
