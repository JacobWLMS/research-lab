<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'
import { useExperiments } from '../../composables/useExperiments'
import { useToast } from '../../composables/useToast'
import type { Experiment, StepStatus } from '../../types'

const props = defineProps<{
  selectedId?: string
}>()

const emit = defineEmits<{
  select: [id: string]
}>()

const { experiments, createExperiment } = useExperiments()
const toast = useToast()

const open = ref(false)
const search = ref('')
const showCreate = ref(false)
const newName = ref('')
const creating = ref(false)
const searchInput = ref<HTMLInputElement | null>(null)
const nameInput = ref<HTMLInputElement | null>(null)

const selectedExperiment = computed(() => {
  if (!props.selectedId) return null
  return experiments.value.find(e => e.id === props.selectedId) ?? null
})

const showSearch = computed(() => experiments.value.length > 5)

const filtered = computed(() => {
  if (!search.value.trim()) return experiments.value
  const q = search.value.toLowerCase()
  return experiments.value.filter(e => e.name.toLowerCase().includes(q))
})

function overallStatus(exp: Experiment): StepStatus {
  const steps = exp.steps
  if (steps.length === 0) return 'pending'
  if (steps.some(s => s.status === 'running')) return 'running'
  if (steps.some(s => s.status === 'failed')) return 'failed'
  if (steps.every(s => s.status === 'completed')) return 'completed'
  return 'pending'
}

function statusColor(status: StepStatus): string {
  switch (status) {
    case 'completed': return 'var(--c-green)'
    case 'running': return 'var(--c-yellow)'
    case 'failed': return 'var(--c-red)'
    default: return 'var(--c-fg-dim)'
  }
}

function stepStatusColor(status: StepStatus): string {
  return statusColor(status)
}

function toggle() {
  open.value = !open.value
  search.value = ''
  showCreate.value = false
  if (open.value) {
    nextTick(() => searchInput.value?.focus())
  }
}

function select(id: string) {
  emit('select', id)
  open.value = false
}

function openCreate() {
  showCreate.value = true
  newName.value = ''
  nextTick(() => nameInput.value?.focus())
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
    open.value = false
    emit('select', exp.id)
    toast.success(`Experiment "${name}" created`)
  }
}

function onClickOutside(e: MouseEvent) {
  const target = e.target as HTMLElement
  if (!target.closest('.exp-selector')) {
    open.value = false
  }
}

watch(open, (v) => {
  if (v) {
    document.addEventListener('click', onClickOutside, true)
  } else {
    document.removeEventListener('click', onClickOutside, true)
  }
})

function headlineMetric(exp: Experiment): string | null {
  // Find the first completed step with metrics
  for (const step of exp.steps) {
    if (step.status === 'completed') return null // We don't have metrics inline here
  }
  return null
}
</script>

<template>
  <div class="exp-selector" @click.stop>
    <button class="exp-selector__trigger" @click="toggle">
      <template v-if="selectedExperiment">
        <span
          class="exp-selector__dot"
          :style="{ background: statusColor(overallStatus(selectedExperiment)) }"
        />
        <span class="exp-selector__name">{{ selectedExperiment.name }}</span>
      </template>
      <template v-else>
        <span class="exp-selector__placeholder">Select experiment...</span>
      </template>
      <svg width="10" height="10" viewBox="0 0 24 24" fill="currentColor" class="exp-selector__chevron">
        <path d="M7 10l5 5 5-5z"/>
      </svg>
    </button>

    <div v-if="open" class="exp-selector__dropdown animate-slide-up">
      <!-- Search -->
      <div v-if="showSearch" class="exp-selector__search">
        <input
          ref="searchInput"
          v-model="search"
          class="exp-selector__search-input"
          placeholder="Filter experiments..."
          @keydown.escape="open = false"
        />
      </div>

      <!-- List -->
      <div class="exp-selector__list">
        <button
          v-for="exp in filtered"
          :key="exp.id"
          class="exp-selector__item"
          :class="{ 'exp-selector__item--active': exp.id === selectedId }"
          @click="select(exp.id)"
        >
          <div class="exp-selector__item-top">
            <span class="exp-selector__item-dot" :style="{ background: statusColor(overallStatus(exp)) }" />
            <span class="exp-selector__item-name">{{ exp.name }}</span>
          </div>
          <div v-if="exp.steps.length > 0" class="exp-selector__item-dots">
            <span
              v-for="step in exp.steps"
              :key="step.name"
              class="exp-selector__pipeline-dot"
              :class="{ 'animate-pulse-glow': step.status === 'running' }"
              :style="{ background: stepStatusColor(step.status) }"
              :title="`${step.title || step.name}: ${step.status}`"
            />
          </div>
        </button>

        <div v-if="filtered.length === 0" class="exp-selector__empty">
          No matching experiments
        </div>
      </div>

      <!-- Create new -->
      <div class="exp-selector__footer">
        <div v-if="showCreate" class="exp-selector__create-form">
          <input
            ref="nameInput"
            v-model="newName"
            class="exp-selector__create-input"
            placeholder="Experiment name..."
            @keydown.enter="doCreate"
            @keydown.escape="showCreate = false"
          />
          <button class="exp-selector__create-submit" :disabled="!newName.trim() || creating" @click="doCreate">
            {{ creating ? '...' : 'Create' }}
          </button>
        </div>
        <button v-else class="exp-selector__create-btn" @click="openCreate">
          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12 5v14m-7-7h14" stroke-linecap="round"/>
          </svg>
          New Experiment
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.exp-selector {
  position: relative;
}

.exp-selector__trigger {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  padding: 0.1875rem 0.5rem;
  font-size: var(--mc-body-size);
  font-weight: 600;
  color: var(--c-fg);
  background: var(--c-bg1);
  border: 1px solid var(--c-border);
  border-radius: var(--radius-sm);
  cursor: pointer;
  max-width: 16rem;
  transition: border-color 0.12s;
}

.exp-selector__trigger:hover {
  border-color: var(--c-fg-dim);
}

.exp-selector__dot {
  width: 0.4375rem;
  height: 0.4375rem;
  border-radius: 50%;
  flex-shrink: 0;
}

.exp-selector__name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.exp-selector__placeholder {
  color: var(--c-fg-dim);
  font-weight: 400;
}

.exp-selector__chevron {
  flex-shrink: 0;
  color: var(--c-fg-dim);
}

/* Dropdown */
.exp-selector__dropdown {
  position: absolute;
  top: 100%;
  left: 0;
  margin-top: 0.25rem;
  width: 18rem;
  background: var(--c-bg);
  border: 1px solid var(--c-border);
  border-radius: var(--radius-md);
  box-shadow: 0 4px 16px rgba(0,0,0,0.3);
  z-index: 200;
  overflow: hidden;
}

.exp-selector__search {
  padding: 0.375rem;
  border-bottom: 1px solid var(--c-border-subtle);
}

.exp-selector__search-input {
  width: 100%;
  font-size: var(--mc-label-size);
  padding: 0.25rem 0.375rem;
  background: var(--c-bg-hard);
  color: var(--c-fg);
  border: 1px solid var(--c-border);
  border-radius: var(--radius-sm);
  outline: none;
}

.exp-selector__search-input:focus {
  border-color: var(--c-aqua);
}

.exp-selector__list {
  max-height: 14rem;
  overflow-y: auto;
}

.exp-selector__item {
  display: flex;
  flex-direction: column;
  gap: 0.125rem;
  width: 100%;
  padding: 0.375rem 0.5rem;
  background: transparent;
  border: none;
  cursor: pointer;
  text-align: left;
  transition: background 0.08s;
  border-bottom: 1px solid var(--c-border-subtle);
}

.exp-selector__item:hover { background: var(--c-surface-hover); }
.exp-selector__item--active { background: var(--c-surface-hover); }

.exp-selector__item-top {
  display: flex;
  align-items: center;
  gap: 0.375rem;
}

.exp-selector__item-dot {
  width: 0.375rem;
  height: 0.375rem;
  border-radius: 50%;
  flex-shrink: 0;
}

.exp-selector__item-name {
  font-size: 0.75rem;
  color: var(--c-fg);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.exp-selector__item-dots {
  display: flex;
  align-items: center;
  gap: 0.125rem;
  padding-left: 0.75rem;
}

.exp-selector__pipeline-dot {
  width: 0.3125rem;
  height: 0.3125rem;
  border-radius: 50%;
  flex-shrink: 0;
}

.exp-selector__empty {
  padding: 1rem;
  text-align: center;
  font-size: var(--mc-label-size);
  color: var(--c-fg-dim);
}

.exp-selector__footer {
  border-top: 1px solid var(--c-border-subtle);
  padding: 0.375rem;
}

.exp-selector__create-btn {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  width: 100%;
  padding: 0.25rem 0.375rem;
  font-size: var(--mc-label-size);
  color: var(--c-aqua);
  background: transparent;
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: background 0.08s;
}

.exp-selector__create-btn:hover { background: var(--c-surface-hover); }

.exp-selector__create-form {
  display: flex;
  align-items: center;
  gap: 0.25rem;
}

.exp-selector__create-input {
  flex: 1;
  font-size: var(--mc-label-size);
  padding: 0.1875rem 0.375rem;
  background: var(--c-bg-hard);
  color: var(--c-fg);
  border: 1px solid var(--c-border);
  border-radius: var(--radius-sm);
  outline: none;
}

.exp-selector__create-input:focus { border-color: var(--c-aqua); }

.exp-selector__create-submit {
  font-size: var(--mc-label-size);
  padding: 0.1875rem 0.5rem;
  background: var(--c-aqua);
  color: var(--c-bg-hard);
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
}

.exp-selector__create-submit:disabled { opacity: 0.4; cursor: not-allowed; }
</style>
