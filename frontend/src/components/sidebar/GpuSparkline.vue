<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import type { WsMessage } from '../../types'
import { useWebSocket } from '../../composables/useWebSocket'

const MAX_POINTS = 60 // ~5 minutes at 5s intervals

interface DataPoint {
  ts: number
  utilization: number
  vram: number
}

const points = ref<DataPoint[]>([])
const { subscribe } = useWebSocket()

const unsubscribe = subscribe((msg: WsMessage) => {
  if (msg.type !== 'gpu_stats') return
  const vramPct = msg.memory_total_gb > 0
    ? (msg.memory_used_gb / msg.memory_total_gb) * 100
    : 0
  points.value = [
    ...points.value,
    { ts: Date.now(), utilization: msg.utilization_pct, vram: vramPct },
  ].slice(-MAX_POINTS)
})

onUnmounted(() => {
  unsubscribe()
})

// SVG dimensions
const W = 200
const H = 60
const PAD = 2

function toPath(values: number[]): string {
  if (values.length === 0) return ''
  const len = values.length
  const xStep = (W - PAD * 2) / Math.max(len - 1, 1)
  return values.map((v, i) => {
    const x = PAD + i * xStep
    const y = H - PAD - ((v / 100) * (H - PAD * 2))
    return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`
  }).join(' ')
}

const utilPath = computed(() => toPath(points.value.map(p => p.utilization)))
const vramPath = computed(() => toPath(points.value.map(p => p.vram)))

const gridLines = [25, 50, 75]

const hasData = computed(() => points.value.length > 1)
const lastUtil = computed(() => points.value.length > 0 ? points.value[points.value.length - 1].utilization : 0)
const lastVram = computed(() => points.value.length > 0 ? points.value[points.value.length - 1].vram : 0)
</script>

<template>
  <div class="gpu-spark">
    <div class="gpu-spark__header">
      <span class="gpu-spark__title">GPU</span>
      <span v-if="hasData" class="gpu-spark__vals">
        <span class="gpu-spark__val gpu-spark__val--util">{{ Math.round(lastUtil) }}%</span>
        <span class="gpu-spark__sep">/</span>
        <span class="gpu-spark__val gpu-spark__val--vram">{{ Math.round(lastVram) }}% VRAM</span>
      </span>
    </div>
    <svg
      class="gpu-spark__chart"
      :viewBox="`0 0 ${W} ${H}`"
      preserveAspectRatio="none"
    >
      <!-- Background grid -->
      <line
        v-for="pct in gridLines"
        :key="pct"
        :x1="PAD"
        :x2="W - PAD"
        :y1="H - PAD - ((pct / 100) * (H - PAD * 2))"
        :y2="H - PAD - ((pct / 100) * (H - PAD * 2))"
        class="gpu-spark__grid"
      />

      <!-- Utilization line (aqua) -->
      <path
        v-if="hasData"
        :d="utilPath"
        class="gpu-spark__line gpu-spark__line--util"
      />

      <!-- VRAM line (green) -->
      <path
        v-if="hasData"
        :d="vramPath"
        class="gpu-spark__line gpu-spark__line--vram"
      />

      <!-- No data -->
      <text
        v-if="!hasData"
        :x="W / 2"
        :y="H / 2 + 3"
        class="gpu-spark__no-data"
      >Waiting for data...</text>
    </svg>
  </div>
</template>

<style scoped>
.gpu-spark {
  padding: var(--mc-panel-pad);
}

.gpu-spark__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.25rem;
}

.gpu-spark__title {
  font-size: 0.5625rem;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--c-fg-dim);
}

.gpu-spark__vals {
  display: flex;
  align-items: center;
  gap: 0.1875rem;
  font-family: var(--font-mono);
  font-size: 0.5625rem;
}

.gpu-spark__val--util {
  color: var(--c-aqua);
}

.gpu-spark__val--vram {
  color: var(--c-green);
}

.gpu-spark__sep {
  color: var(--c-fg-dim);
}

.gpu-spark__chart {
  width: 100%;
  height: 3.75rem;
  display: block;
}

.gpu-spark__grid {
  stroke: var(--c-border-subtle);
  stroke-width: 0.5;
  stroke-dasharray: 2 2;
}

.gpu-spark__line {
  fill: none;
  stroke-width: 1.5;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.gpu-spark__line--util {
  stroke: var(--c-aqua);
}

.gpu-spark__line--vram {
  stroke: var(--c-green);
  opacity: 0.7;
}

.gpu-spark__no-data {
  font-size: 8px;
  fill: var(--c-fg-dim);
  text-anchor: middle;
}
</style>
