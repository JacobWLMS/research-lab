<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useExperiments } from '../../composables/useExperiments'
import StatusBadge from '../shared/StatusBadge.vue'
import type { Experiment, StepStatus, SortField } from '../../types'

const props = defineProps<{
  selectedId?: string
}>()

const emit = defineEmits<{
  select: [id: string]
}>()

const { experiments, loading, sortField, sortAsc, fetchExperiments, createExperiment, setSort } = useExperiments()

// Create experiment dialog
const showCreate = ref(false)
const newName = ref('')
const creating = ref(false)
const nameInput = ref<HTMLInputElement | null>(null)

onMounted(() => {
  fetchExperiments()
})

function overallStatus(exp: Experiment): StepStatus {
  const steps = exp.steps
  if (steps.length === 0) return 'pending'
  if (steps.some((s) => s.status === 'running')) return 'running'
  if (steps.some((s) => s.status === 'failed')) return 'failed'
  if (steps.every((s) => s.status === 'completed')) return 'completed'
  return 'pending'
}

function stepCount(exp: Experiment): number {
  return exp.steps.length
}

function formatTime(iso: string): string {
  const d = new Date(iso)
  const now = new Date()
  const ms = now.getTime() - d.getTime()
  const min = Math.floor(ms / 60_000)
  if (min < 1) return 'now'
  if (min < 60) return `${min}m`
  const h = Math.floor(min / 60)
  if (h < 24) return `${h}h`
  const d2 = Math.floor(h / 24)
  return `${d2}d`
}

function sortArrow(field: SortField): string {
  if (sortField.value !== field) return ''
  return sortAsc.value ? '\u25B4' : '\u25BE'
}

async function doCreate() {
  const name = newName.value.trim()
  if (!name || creating.value) return
  creating.value = true
  const exp = await createExperiment(name)
  creating.value = false
  if (exp) {
    showCreate.value = false
    newName.value = ''
    emit('select', exp.id)
  }
}

function openCreate() {
  showCreate.value = true
  newName.value = ''
  setTimeout(() => nameInput.value?.focus(), 50)
}
</script>

<template>
  <div class="flex flex-col h-full">
    <!-- Header with count + create button -->
    <div
      class="flex items-center justify-between px-3 py-1.5 border-b shrink-0"
      style="border-color: var(--color-bg2)"
    >
      <span class="text-xs font-medium" style="color: var(--color-fg-muted)">
        Experiments
        <span class="font-mono ml-1" style="color: var(--color-fg-dim)">{{ experiments.length }}</span>
      </span>
      <button
        class="flex items-center gap-0.5 text-xs px-1.5 py-0.5 cursor-pointer"
        style="color: var(--color-aqua); background: transparent; border-radius: 2px; transition: background 0.12s"
        @click="openCreate"
        @mouseenter="($event.currentTarget as HTMLElement).style.background = 'var(--color-bg1)'"
        @mouseleave="($event.currentTarget as HTMLElement).style.background = 'transparent'"
      >
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M12 5v14m-7-7h14" stroke-linecap="round"/>
        </svg>
        New
      </button>
    </div>

    <!-- Create experiment inline form -->
    <div
      v-if="showCreate"
      class="px-3 py-2 border-b animate-slide-up"
      style="border-color: var(--color-bg2); background: var(--color-bg1)"
    >
      <div class="flex items-center gap-1.5">
        <input
          ref="nameInput"
          v-model="newName"
          class="flex-1 text-xs px-2 py-1 outline-none border"
          style="
            background: var(--color-bg-hard);
            color: var(--color-fg);
            border-color: var(--color-bg2);
            border-radius: 2px;
          "
          placeholder="Experiment name..."
          @keydown.enter="doCreate"
          @keydown.escape="showCreate = false"
        />
        <button
          class="text-xs px-2 py-1 cursor-pointer shrink-0"
          :style="{
            background: !newName.trim() || creating ? 'var(--color-bg2)' : 'var(--color-aqua)',
            color: !newName.trim() || creating ? 'var(--color-fg-dim)' : 'var(--color-bg-hard)',
            borderRadius: '2px',
            opacity: !newName.trim() || creating ? 0.5 : 1,
          }"
          :disabled="!newName.trim() || creating"
          @click="doCreate"
        >{{ creating ? '...' : 'Create' }}</button>
        <button
          class="text-xs px-1.5 py-1 cursor-pointer"
          style="color: var(--color-fg-dim); background: transparent; border-radius: 2px"
          @click="showCreate = false"
        >
          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M18 6L6 18M6 6l12 12" stroke-linecap="round"/>
          </svg>
        </button>
      </div>
    </div>

    <!-- Loading -->
    <div
      v-if="loading && experiments.length === 0"
      class="flex items-center justify-center py-8 text-xs"
      style="color: var(--color-fg-dim)"
    >Loading...</div>

    <!-- Column headers -->
    <div
      v-if="experiments.length > 0"
      class="grid gap-1 px-3 py-1 text-[10px] uppercase tracking-wider border-b shrink-0 select-none"
      style="grid-template-columns: 20px 1fr 32px 40px; border-color: var(--color-bg1); color: var(--color-fg-dim)"
    >
      <span class="cursor-pointer" @click="setSort('status')">{{ sortArrow('status') }}</span>
      <span class="cursor-pointer" @click="setSort('name')">Name {{ sortArrow('name') }}</span>
      <span class="cursor-pointer text-center" @click="setSort('status')">St</span>
      <span class="cursor-pointer text-right" @click="setSort('updated_at')">
        Age {{ sortArrow('updated_at') }}
      </span>
    </div>

    <!-- List -->
    <div class="flex-1 overflow-y-auto">
      <button
        v-for="exp in experiments"
        :key="exp.id"
        class="w-full grid gap-1 items-center px-3 py-1.5 text-left text-xs border-b cursor-pointer"
        :style="{
          gridTemplateColumns: '20px 1fr 32px 40px',
          borderColor: 'var(--color-bg1)',
          background: exp.id === selectedId ? 'var(--color-bg1)' : 'transparent',
          transition: 'background 0.08s',
        }"
        @click="emit('select', exp.id)"
        @mouseenter="($event.currentTarget as HTMLElement).style.background = exp.id === selectedId ? 'var(--color-bg1)' : 'var(--color-bg)'"
        @mouseleave="($event.currentTarget as HTMLElement).style.background = exp.id === selectedId ? 'var(--color-bg1)' : 'transparent'"
      >
        <StatusBadge :status="overallStatus(exp)" :show-label="false" />
        <span class="truncate" style="color: var(--color-fg)">{{ exp.name }}</span>
        <span class="font-mono text-center" style="color: var(--color-fg-muted)">{{ stepCount(exp) }}</span>
        <span class="text-right whitespace-nowrap" style="color: var(--color-fg-dim)">
          {{ formatTime(exp.updated_at) }}
        </span>
      </button>
    </div>

    <!-- Empty state -->
    <div
      v-if="!loading && experiments.length === 0"
      class="flex flex-col items-center justify-center py-8 gap-2 text-xs"
      style="color: var(--color-fg-dim)"
    >
      <span>No experiments yet</span>
      <button
        class="px-2 py-1 cursor-pointer text-xs"
        style="color: var(--color-aqua); background: var(--color-bg1); border-radius: 2px"
        @click="openCreate"
      >Create one</button>
    </div>
  </div>
</template>
