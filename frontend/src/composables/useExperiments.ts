import { ref, computed } from 'vue'
import type { Experiment, SortField, WsMessage } from '../types'
import { useWebSocket } from './useWebSocket'

// Singleton state
const experiments = ref<Experiment[]>([])
const loading = ref(false)
const error = ref<string | null>(null)
const sortField = ref<SortField>('updated_at')
const sortAsc = ref(false)

// Auto-refresh on WebSocket events — subscribe once
let wsSubscribed = false
function ensureWsSubscription() {
  if (wsSubscribed) return
  wsSubscribed = true
  const { subscribe } = useWebSocket()
  subscribe((msg: WsMessage) => {
    switch (msg.type) {
      case 'experiment_created':
      case 'step_added':
      case 'step_started':
      case 'step_completed':
      case 'pipeline_completed':
        // Refresh the experiment list on any mutation
        fetchExperiments()
        break
    }
  })
}

function statusWeight(exp: Experiment): number {
  const steps = exp.steps
  if (steps.some((s) => s.status === 'running')) return 0
  if (steps.some((s) => s.status === 'failed')) return 1
  if (steps.every((s) => s.status === 'completed') && steps.length > 0) return 3
  return 2
}

const sorted = computed(() => {
  const field = sortField.value
  const asc = sortAsc.value

  return [...experiments.value].sort((a, b) => {
    let cmp = 0
    switch (field) {
      case 'name':
        cmp = a.name.localeCompare(b.name)
        break
      case 'updated_at':
        cmp = a.updated_at.localeCompare(b.updated_at)
        break
      case 'created_at':
        cmp = a.created_at.localeCompare(b.created_at)
        break
      case 'status':
        cmp = statusWeight(a) - statusWeight(b)
        break
      default:
        cmp = 0
    }
    return asc ? cmp : -cmp
  })
})

async function fetchExperiments() {
  loading.value = true
  error.value = null
  try {
    const res = await fetch('/api/experiments')
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    experiments.value = await res.json()
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    loading.value = false
  }
}

async function createExperiment(name: string): Promise<Experiment | null> {
  error.value = null
  try {
    const res = await fetch('/api/experiments', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const exp: Experiment = await res.json()
    await fetchExperiments()
    return exp
  } catch (e) {
    error.value = (e as Error).message
    return null
  }
}

async function deleteExperiment(id: string): Promise<boolean> {
  error.value = null
  try {
    const res = await fetch(`/api/experiments/${id}`, { method: 'DELETE' })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    await fetchExperiments()
    return true
  } catch (e) {
    error.value = (e as Error).message
    return false
  }
}

function setSort(field: SortField) {
  if (sortField.value === field) {
    sortAsc.value = !sortAsc.value
  } else {
    sortField.value = field
    sortAsc.value = field === 'name'
  }
}

export function useExperiments() {
  ensureWsSubscription()
  return {
    experiments: sorted,
    raw: experiments,
    loading,
    error,
    sortField,
    sortAsc,
    fetchExperiments,
    createExperiment,
    deleteExperiment,
    setSort,
  }
}
