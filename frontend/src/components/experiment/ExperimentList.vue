<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useExperiments } from '../../composables/useExperiments'
import { useWebSocket } from '../../composables/useWebSocket'
import { useToast } from '../../composables/useToast'
import StatusBadge from '../shared/StatusBadge.vue'
import type { Experiment, StepStatus, SortField, WsMessage } from '../../types'

const props = defineProps<{
  selectedId?: string
}>()

const emit = defineEmits<{
  select: [id: string]
}>()

const { experiments, loading, sortField, sortAsc, fetchExperiments, createExperiment, deleteExperiment, setSort } = useExperiments()
const { subscribe } = useWebSocket()
const toast = useToast()

// Create experiment dialog
const showCreate = ref(false)
const newName = ref('')
const creating = ref(false)
const nameInput = ref<HTMLInputElement | null>(null)

// Delete confirmation
const confirmDeleteId = ref<string | null>(null)

onMounted(() => {
  fetchExperiments()
})

// Auto-refresh on relevant WS events
const unsubscribe = subscribe((msg: WsMessage) => {
  if (
    msg.type === 'step_completed' ||
    msg.type === 'step_started' ||
    msg.type === 'pipeline_completed'
  ) {
    fetchExperiments()
  }
})

onUnmounted(() => {
  unsubscribe()
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
    toast.success(`Experiment "${name}" created`)
  }
}

function openCreate() {
  showCreate.value = true
  newName.value = ''
  setTimeout(() => nameInput.value?.focus(), 50)
}

async function doDelete(id: string) {
  const ok = await deleteExperiment(id)
  confirmDeleteId.value = null
  if (ok) {
    toast.info('Experiment deleted')
  }
}
</script>

<template>
  <div class="exp-list">
    <!-- Header with count + create button -->
    <div class="exp-list__header">
      <span class="exp-list__label">
        Experiments
        <span class="exp-list__count">{{ experiments.length }}</span>
      </span>
      <button
        class="exp-list__create-btn"
        @click="openCreate"
        title="Create new experiment"
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
      class="exp-list__create-form animate-slide-up"
    >
      <div class="exp-list__create-form-row">
        <input
          ref="nameInput"
          v-model="newName"
          class="exp-list__input"
          placeholder="Experiment name..."
          @keydown.enter="doCreate"
          @keydown.escape="showCreate = false"
        />
        <button
          class="exp-list__submit-btn"
          :disabled="!newName.trim() || creating"
          @click="doCreate"
        >{{ creating ? '...' : 'Create' }}</button>
        <button class="exp-list__cancel-btn" @click="showCreate = false">
          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M18 6L6 18M6 6l12 12" stroke-linecap="round"/>
          </svg>
        </button>
      </div>
    </div>

    <!-- Skeleton loading -->
    <div v-if="loading && experiments.length === 0" class="exp-list__skeleton">
      <div v-for="i in 5" :key="i" class="exp-list__skeleton-row">
        <div class="skeleton" style="width: 0.5rem; height: 0.5rem; border-radius: 50%"></div>
        <div class="skeleton" :style="{ width: (40 + i * 12) + '%', height: '0.75rem' }"></div>
        <div class="skeleton" style="width: 1.5rem; height: 0.75rem; margin-left: auto"></div>
      </div>
    </div>

    <!-- Column headers -->
    <div
      v-if="experiments.length > 0"
      class="exp-list__col-headers no-select"
    >
      <span class="exp-list__col-hdr" @click="setSort('status')">{{ sortArrow('status') }}</span>
      <span class="exp-list__col-hdr exp-list__col-hdr--name" @click="setSort('name')">Name {{ sortArrow('name') }}</span>
      <span class="exp-list__col-hdr exp-list__col-hdr--count" @click="setSort('status')">St</span>
      <span class="exp-list__col-hdr exp-list__col-hdr--age" @click="setSort('updated_at')">
        Age {{ sortArrow('updated_at') }}
      </span>
    </div>

    <!-- List -->
    <div class="exp-list__items">
      <div
        v-for="(exp, index) in experiments"
        :key="exp.id"
        class="exp-list__item"
        :class="{ 'exp-list__item--selected': exp.id === selectedId }"
        :style="{ animationDelay: index * 20 + 'ms' }"
        @click="emit('select', exp.id)"
        @contextmenu.prevent="confirmDeleteId = confirmDeleteId === exp.id ? null : exp.id"
      >
        <StatusBadge :status="overallStatus(exp)" :show-label="false" />
        <span class="exp-list__item-name">{{ exp.name }}</span>
        <span class="exp-list__item-steps">{{ stepCount(exp) }}</span>
        <span class="exp-list__item-age">{{ formatTime(exp.updated_at) }}</span>

        <!-- Delete confirmation overlay -->
        <div
          v-if="confirmDeleteId === exp.id"
          class="exp-list__delete-confirm"
          @click.stop
        >
          <span>Delete?</span>
          <button class="exp-list__delete-yes" @click.stop="doDelete(exp.id)">Yes</button>
          <button class="exp-list__delete-no" @click.stop="confirmDeleteId = null">No</button>
        </div>
      </div>
    </div>

    <!-- Empty state -->
    <div
      v-if="!loading && experiments.length === 0"
      class="exp-list__empty"
    >
      <span>No experiments yet</span>
      <button class="exp-list__empty-btn" @click="openCreate">Create one</button>
    </div>
  </div>
</template>

<style scoped>
.exp-list {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.exp-list__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.375rem 0.75rem;
  border-bottom: 1px solid var(--c-border-subtle);
  flex-shrink: 0;
}

.exp-list__label {
  font-size: 0.75rem;
  font-weight: 500;
  color: var(--c-fg-muted);
}

.exp-list__count {
  font-family: var(--font-mono);
  margin-left: 0.25rem;
  color: var(--c-fg-dim);
}

.exp-list__create-btn {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  font-size: 0.75rem;
  padding: 0.125rem 0.375rem;
  color: var(--c-aqua);
  background: transparent;
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: background 0.12s;
}

.exp-list__create-btn:hover {
  background: var(--c-surface-hover);
}

/* Create form */
.exp-list__create-form {
  padding: 0.5rem 0.75rem;
  border-bottom: 1px solid var(--c-border-subtle);
  background: var(--c-bg1);
}

.exp-list__create-form-row {
  display: flex;
  align-items: center;
  gap: 0.375rem;
}

.exp-list__input {
  flex: 1;
  font-size: 0.75rem;
  padding: 0.25rem 0.5rem;
  background: var(--c-bg-hard);
  color: var(--c-fg);
  border: 1px solid var(--c-border);
  border-radius: var(--radius-sm);
  outline: none;
}

.exp-list__input:focus {
  border-color: var(--c-aqua);
}

.exp-list__submit-btn {
  font-size: 0.75rem;
  padding: 0.25rem 0.5rem;
  background: var(--c-aqua);
  color: var(--c-bg-hard);
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
  flex-shrink: 0;
  transition: opacity 0.12s;
}

.exp-list__submit-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.exp-list__cancel-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0.25rem;
  color: var(--c-fg-dim);
  background: transparent;
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
}

.exp-list__cancel-btn:hover {
  color: var(--c-fg);
}

/* Skeleton */
.exp-list__skeleton {
  padding: 0.5rem 0.75rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.exp-list__skeleton-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

/* Column headers */
.exp-list__col-headers {
  display: grid;
  grid-template-columns: 1.25rem 1fr 2rem 2.5rem;
  gap: 0.25rem;
  padding: 0.25rem 0.75rem;
  font-size: 0.625rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  border-bottom: 1px solid var(--c-border-subtle);
  flex-shrink: 0;
  color: var(--c-fg-dim);
}

.exp-list__col-hdr {
  cursor: pointer;
  transition: color 0.08s;
}

.exp-list__col-hdr:hover {
  color: var(--c-fg-muted);
}

.exp-list__col-hdr--count {
  text-align: center;
}

.exp-list__col-hdr--age {
  text-align: right;
}

/* Items */
.exp-list__items {
  flex: 1;
  overflow-y: auto;
}

.exp-list__item {
  display: grid;
  grid-template-columns: 1.25rem 1fr 2rem 2.5rem;
  gap: 0.25rem;
  align-items: center;
  padding: 0.375rem 0.75rem;
  font-size: 0.75rem;
  border-bottom: 1px solid var(--c-border-subtle);
  cursor: pointer;
  transition: background 0.08s;
  position: relative;
  animation: fade-in 0.15s ease both;
}

.exp-list__item:hover {
  background: var(--c-surface-hover);
}

.exp-list__item--selected {
  background: var(--c-surface-hover);
}

.exp-list__item--selected:hover {
  background: var(--c-surface-active);
}

.exp-list__item-name {
  color: var(--c-fg);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.exp-list__item-steps {
  font-family: var(--font-mono);
  text-align: center;
  color: var(--c-fg-muted);
}

.exp-list__item-age {
  text-align: right;
  white-space: nowrap;
  color: var(--c-fg-dim);
}

/* Delete confirmation */
.exp-list__delete-confirm {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  background: var(--c-bg);
  font-size: 0.6875rem;
  color: var(--c-fg-muted);
  animation: fade-in 0.1s ease;
  z-index: 2;
}

.exp-list__delete-yes {
  font-size: 0.6875rem;
  padding: 0.125rem 0.5rem;
  background: var(--c-red);
  color: var(--c-bg-hard);
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
}

.exp-list__delete-no {
  font-size: 0.6875rem;
  padding: 0.125rem 0.5rem;
  background: var(--c-bg2);
  color: var(--c-fg);
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
}

/* Empty state */
.exp-list__empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 2rem 0;
  gap: 0.5rem;
  font-size: 0.75rem;
  color: var(--c-fg-dim);
}

.exp-list__empty-btn {
  padding: 0.25rem 0.5rem;
  font-size: 0.75rem;
  color: var(--c-aqua);
  background: var(--c-bg1);
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: background 0.12s;
}

.exp-list__empty-btn:hover {
  background: var(--c-surface-hover);
}
</style>
