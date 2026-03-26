<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useActivityFeed, type ActivityEntry } from '../../composables/useActivityFeed'
import { useRouter } from 'vue-router'
import GpuSparkline from './GpuSparkline.vue'

const props = defineProps<{
  liveMetrics?: Record<string, Record<string, number | string>>
  experimentId?: string | null
}>()

const { feed } = useActivityFeed()
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

// Aggregate all live metrics from all running steps into a flat list
const flatLiveMetrics = computed(() => {
  const entries: { stepName: string; key: string; value: number | string }[] = []
  if (!props.liveMetrics) return entries
  for (const [stepName, metrics] of Object.entries(props.liveMetrics)) {
    for (const [key, value] of Object.entries(metrics)) {
      entries.push({ stepName, key, value })
    }
  }
  return entries
})

const hasLiveMetrics = computed(() => flatLiveMetrics.value.length > 0)

function formatMetricValue(val: number | string): string {
  if (typeof val === 'number') {
    if (Number.isInteger(val)) return String(val)
    return val.toFixed(4)
  }
  return String(val)
}
</script>

<template>
  <div class="activity-sidebar">
    <!-- Activity Feed -->
    <div class="activity-sidebar__section activity-sidebar__feed">
      <div class="activity-sidebar__section-header">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        <span>Activity</span>
      </div>

      <div v-if="feed.length === 0" class="activity-sidebar__empty">
        No activity yet
      </div>

      <div v-else class="activity-sidebar__feed-list">
        <div
          v-for="entry in feed"
          :key="entry.id"
          class="activity-sidebar__feed-item"
          :class="{ 'activity-sidebar__feed-item--clickable': !!entry.experimentId }"
          @click="navigateToEvent(entry)"
        >
          <span
            class="activity-sidebar__feed-dot"
            :style="{ background: eventColor(entry.type) }"
          />
          <div class="activity-sidebar__feed-content">
            <span class="activity-sidebar__feed-msg">{{ entry.message }}</span>
          </div>
          <span class="activity-sidebar__feed-time">{{ relativeTime(entry.timestamp) }}</span>
        </div>
      </div>
    </div>

    <!-- Live Metrics -->
    <div v-if="hasLiveMetrics" class="activity-sidebar__section activity-sidebar__metrics">
      <div class="activity-sidebar__section-header">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M22 12h-4l-3 9L9 3l-3 9H2" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        <span>Live Metrics</span>
      </div>

      <div class="activity-sidebar__metrics-list">
        <div
          v-for="m in flatLiveMetrics"
          :key="`${m.stepName}-${m.key}`"
          class="activity-sidebar__metric"
        >
          <span class="activity-sidebar__metric-key">{{ m.key }}</span>
          <span class="activity-sidebar__metric-val">{{ formatMetricValue(m.value) }}</span>
        </div>
      </div>
    </div>

    <!-- GPU Sparkline -->
    <div class="activity-sidebar__section activity-sidebar__gpu">
      <GpuSparkline />
    </div>
  </div>
</template>

<style scoped>
.activity-sidebar {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

.activity-sidebar__section {
  border-bottom: var(--mc-panel-border);
}

.activity-sidebar__section-header {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  padding: 0.5rem var(--mc-panel-pad);
  font-size: 0.5625rem;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--c-fg-dim);
  border-bottom: 1px solid var(--c-border-subtle);
}

/* Feed */
.activity-sidebar__feed {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  max-height: 50%;
}

.activity-sidebar__feed-list {
  flex: 1;
  overflow-y: auto;
}

.activity-sidebar__empty {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1.5rem 0;
  font-size: var(--mc-label-size);
  color: var(--c-fg-dim);
}

.activity-sidebar__feed-item {
  display: flex;
  align-items: flex-start;
  gap: 0.375rem;
  padding: 0.3125rem var(--mc-panel-pad);
  transition: background 0.08s;
}

.activity-sidebar__feed-item--clickable {
  cursor: pointer;
}

.activity-sidebar__feed-item--clickable:hover {
  background: var(--c-surface-hover);
}

.activity-sidebar__feed-dot {
  width: 0.375rem;
  height: 0.375rem;
  border-radius: 50%;
  flex-shrink: 0;
  margin-top: 0.25rem;
}

.activity-sidebar__feed-content {
  flex: 1;
  min-width: 0;
}

.activity-sidebar__feed-msg {
  font-size: var(--mc-label-size);
  color: var(--c-fg);
  line-height: 1.3;
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
}

.activity-sidebar__feed-time {
  font-size: 0.5625rem;
  color: var(--c-fg-dim);
  white-space: nowrap;
  flex-shrink: 0;
  margin-top: 0.0625rem;
}

/* Live Metrics */
.activity-sidebar__metrics {
  flex-shrink: 0;
}

.activity-sidebar__metrics-list {
  display: flex;
  flex-wrap: wrap;
  gap: var(--mc-gap-xs);
  padding: var(--mc-panel-pad);
}

.activity-sidebar__metric {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.0625rem;
  padding: 0.1875rem 0.375rem;
  background: var(--c-bg1);
  border: 1px solid var(--c-border-subtle);
  border-radius: var(--radius-sm);
  min-width: 3.5rem;
}

.activity-sidebar__metric-key {
  font-size: 0.5625rem;
  color: var(--c-fg-dim);
  text-transform: uppercase;
  letter-spacing: 0.02em;
}

.activity-sidebar__metric-val {
  font-size: var(--mc-label-size);
  font-family: var(--font-mono);
  font-weight: 600;
  color: var(--c-fg);
}

/* GPU */
.activity-sidebar__gpu {
  flex-shrink: 0;
  border-bottom: none;
  margin-top: auto;
}
</style>
