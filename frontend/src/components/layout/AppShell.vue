<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useWebSocket } from '../../composables/useWebSocket'
import { useGpuStats } from '../../composables/useGpuStats'
import { useExperiments } from '../../composables/useExperiments'
import ExperimentList from '../experiment/ExperimentList.vue'

const router = useRouter()
const route = useRoute()
const { connected, connect } = useWebSocket()
const { gpu } = useGpuStats()
const { fetchExperiments } = useExperiments()

const panelWidth = ref(260)
const isResizing = ref(false)
const MIN_W = 180
const MAX_W = 450

function onMouseDown(e: MouseEvent) {
  isResizing.value = true
  e.preventDefault()
}

function onMouseMove(e: MouseEvent) {
  if (!isResizing.value) return
  panelWidth.value = Math.min(Math.max(e.clientX, MIN_W), MAX_W)
}

function onMouseUp() {
  isResizing.value = false
}

function selectExperiment(id: string) {
  router.push({ name: 'experiment', params: { id } })
}

onMounted(() => {
  connect()
  fetchExperiments()
  document.addEventListener('mousemove', onMouseMove)
  document.addEventListener('mouseup', onMouseUp)
})

onUnmounted(() => {
  document.removeEventListener('mousemove', onMouseMove)
  document.removeEventListener('mouseup', onMouseUp)
})
</script>

<template>
  <div class="flex flex-col h-screen overflow-hidden">
    <!-- Top bar -->
    <header
      class="flex items-center justify-between px-4 h-9 shrink-0 border-b"
      style="background: var(--color-bg); border-color: var(--color-bg2)"
    >
      <!-- Left: project name -->
      <div class="flex items-center gap-2">
        <span class="font-semibold text-sm tracking-tight" style="color: var(--color-aqua)">research-lab</span>
      </div>

      <!-- Center: GPU stats -->
      <div
        v-if="gpu"
        class="flex items-center gap-3 text-xs"
        style="color: var(--color-fg-muted)"
      >
        <span>
          GPU
          <span class="font-mono" style="color: var(--color-fg)">{{ gpu.utilization_pct }}%</span>
        </span>
        <span style="color: var(--color-bg3)">|</span>
        <span>
          VRAM
          <span class="font-mono" style="color: var(--color-fg)">
            {{ gpu.memory_used_gb.toFixed(1) }}/{{ gpu.memory_total_gb.toFixed(0) }}GB
          </span>
        </span>
        <span style="color: var(--color-bg3)">|</span>
        <span class="font-mono" style="color: var(--color-fg)">{{ gpu.temperature_c }}&deg;C</span>
      </div>
      <div v-else class="text-xs" style="color: var(--color-fg-dim)">No GPU</div>

      <!-- Right: connection -->
      <div class="flex items-center gap-1.5">
        <span
          class="w-2 h-2 rounded-full"
          :style="{ background: connected ? 'var(--color-green)' : 'var(--color-red)', transition: 'background 0.12s' }"
        />
        <span class="text-xs" style="color: var(--color-fg-muted)">
          {{ connected ? 'Connected' : 'Disconnected' }}
        </span>
      </div>
    </header>

    <!-- Main content -->
    <div class="flex flex-1 overflow-hidden">
      <!-- Left panel -->
      <aside
        class="shrink-0 overflow-y-auto border-r"
        :style="{
          width: panelWidth + 'px',
          background: 'var(--color-bg-hard)',
          borderColor: 'var(--color-bg2)',
        }"
      >
        <ExperimentList
          :selected-id="typeof route.params.id === 'string' ? route.params.id : undefined"
          @select="selectExperiment"
        />
      </aside>

      <!-- Resize handle -->
      <div
        class="w-px cursor-col-resize shrink-0"
        :style="{
          background: isResizing ? 'var(--color-aqua)' : 'var(--color-bg2)',
          transition: 'background 0.12s',
        }"
        @mousedown="onMouseDown"
        @mouseenter="($event.currentTarget as HTMLElement).style.background = 'var(--color-aqua)'"
        @mouseleave="!isResizing && (($event.currentTarget as HTMLElement).style.background = 'var(--color-bg2)')"
      />

      <!-- Right panel -->
      <main class="flex-1 overflow-hidden" style="background: var(--color-bg-hard)">
        <slot />
      </main>
    </div>
  </div>
</template>
