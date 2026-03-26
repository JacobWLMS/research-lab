import { ref, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import type {
  Experiment,
  Step,
  StepResult,
  CanvasData,
  WsMessage,
  StepStatus,
} from '../types'
import { useWebSocket } from './useWebSocket'
import { useToast } from './useToast'
import { useExperiments } from './useExperiments'

// ---------------------------------------------------------------------------
// Module-scope singleton state — survives component mount/unmount cycles.
// Every call to useExperimentDetail() returns the SAME refs.
// ---------------------------------------------------------------------------
const experiment = ref<Experiment | null>(null)
const results = ref<Record<string, StepResult>>({})
const canvases = ref<Record<string, CanvasData[]>>({})
const outputLines = ref<Record<string, string[]>>({})
const liveMetrics = ref<Record<string, Record<string, number | string>>>({})
const progress = ref<Record<string, { current: number; total: number; eta_s?: number }>>({})
const loading = ref(false)
const error = ref<string | null>(null)
const pipelineRunning = ref(false)

// Track which experiment the singleton is currently loaded for, and whether
// the WebSocket subscription has been wired up.
let currentExperimentId: string | null = null
let wsSubscribed = false

// ---------------------------------------------------------------------------
// Helpers (module-private)
// ---------------------------------------------------------------------------

function findStep(name: string): Step | undefined {
  return experiment.value?.steps.find((s) => s.name === name)
}

/**
 * After fetchExperiment() replaces `experiment.value` wholesale, merge live
 * step statuses that the WebSocket may have set (e.g. "running") into the
 * fresh data so we don't lose in-flight status changes.
 */
function mergeStepStatuses(fresh: Experiment, liveStatuses: Map<string, StepStatus>): Experiment {
  for (const step of fresh.steps) {
    const live = liveStatuses.get(step.name)
    // If the WebSocket said the step is "running" but the server still says
    // "pending", keep the optimistic "running" flag.
    if (live === 'running' && step.status !== 'running') {
      step.status = live
    }
  }
  return fresh
}

/**
 * Hydrate `outputLines` from persisted result stdout/stderr so that log
 * output survives refresh and navigation.
 */
function hydrateOutputFromResults() {
  for (const [stepName, result] of Object.entries(results.value)) {
    // Only fill in if we have no live lines for this step yet (don't
    // overwrite a currently-streaming step).
    if (result.stdout && (!outputLines.value[stepName] || outputLines.value[stepName].length === 0)) {
      outputLines.value = {
        ...outputLines.value,
        [stepName]: result.stdout.split('\n').filter(Boolean),
      }
    }
  }
}

// ---------------------------------------------------------------------------
// API helpers
// ---------------------------------------------------------------------------

async function fetchExperiment(id: string) {
  // Lazily grab singletons — safe because these are also module-scoped singletons.
  const toast = useToast()
  const router = useRouter()

  loading.value = true
  error.value = null

  // Snapshot running statuses so we can merge them after the fetch
  const liveStatuses = new Map<string, StepStatus>()
  if (experiment.value) {
    for (const step of experiment.value.steps) {
      if (step.status === 'running') {
        liveStatuses.set(step.name, step.status)
      }
    }
  }

  try {
    const res = await fetch(`/api/experiments/${id}`)
    if (res.status === 404) {
      experiment.value = null
      toast.info('Experiment not found')
      router.push('/')
      return
    }
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const fresh: Experiment = await res.json()
    experiment.value = mergeStepStatuses(fresh, liveStatuses)
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    loading.value = false
  }
}

async function fetchResults(id: string) {
  try {
    const res = await fetch(`/api/experiments/${id}/results`)
    if (!res.ok) return
    const data = await res.json()
    if (data && typeof data === 'object' && !Array.isArray(data)) {
      results.value = data as Record<string, StepResult>

      // Populate canvases from results — critical for persistence after
      // navigation. Canvases are stored in result JSON on disk.
      const newCanvases: Record<string, CanvasData[]> = {}
      for (const [stepName, result] of Object.entries(data)) {
        const r = result as any
        if (r?.canvases && Array.isArray(r.canvases) && r.canvases.length > 0) {
          newCanvases[stepName] = r.canvases.map((c: any) => ({
            name: c.canvas_name || c.name || 'Output',
            widgets: c.widgets || [],
          }))
        }
      }
      // Merge: persisted canvases first, live updates win on conflict
      canvases.value = { ...newCanvases, ...canvases.value }

      // Hydrate output lines from result stdout so logs persist across
      // refresh and navigation.
      hydrateOutputFromResults()
    }
  } catch {
    // non-fatal
  }
}

// No-op: summaries from fetchResults() are sufficient for the UI.
// Full canvas data is lazy-loaded by CanvasReport.vue per-step.
async function fetchStepCanvases(_id: string) {}

// ---------------------------------------------------------------------------
// WebSocket subscription — wired up exactly once for the singleton.
// ---------------------------------------------------------------------------

function ensureWsSubscription(experimentId: () => string | null) {
  if (wsSubscribed) return
  wsSubscribed = true

  const { subscribe } = useWebSocket()
  const toast = useToast()
  const { fetchExperiments } = useExperiments()

  subscribe((msg: WsMessage) => {
    const id = experimentId()
    if (!id) return

    // Filter to current experiment (except gpu_stats which is global)
    if ('experiment_id' in msg && msg.experiment_id !== id) return

    switch (msg.type) {
      case 'step_started': {
        const step = findStep(msg.step_name)
        if (step) step.status = 'running' as StepStatus
        outputLines.value = { ...outputLines.value, [msg.step_name]: [] }
        liveMetrics.value = { ...liveMetrics.value, [msg.step_name]: {} }
        progress.value = { ...progress.value, [msg.step_name]: { current: 0, total: 0 } }
        break
      }

      case 'stdout': {
        if (!outputLines.value[msg.step_name]) outputLines.value[msg.step_name] = []
        outputLines.value[msg.step_name] = [...outputLines.value[msg.step_name], msg.text]
        break
      }

      case 'stderr': {
        if (!outputLines.value[msg.step_name]) outputLines.value[msg.step_name] = []
        outputLines.value[msg.step_name] = [...outputLines.value[msg.step_name], msg.text]
        break
      }

      case 'step_completed': {
        const step = findStep(msg.step_name)
        if (step) step.status = msg.status as StepStatus
        fetchResults(id).then(() => fetchStepCanvases(id))
        fetchExperiments()
        if (msg.status === 'completed') {
          toast.success(`Step "${msg.step_name}" completed (${msg.duration_s.toFixed(1)}s)`)
        } else {
          toast.error(`Step "${msg.step_name}" failed`)
        }
        break
      }

      case 'metrics_live': {
        liveMetrics.value[msg.step_name] = {
          ...liveMetrics.value[msg.step_name],
          ...msg.data,
        }
        break
      }

      case 'canvas_update': {
        if (!canvases.value[msg.step_name]) canvases.value[msg.step_name] = []
        const arr = canvases.value[msg.step_name]
        const idx = arr.findIndex((c) => c.name === msg.canvas_name)
        const canvas: CanvasData = { name: msg.canvas_name, widgets: msg.widgets }
        if (idx >= 0) {
          arr[idx] = canvas
        } else {
          arr.push(canvas)
        }
        break
      }

      case 'progress': {
        progress.value[msg.step_name] = {
          current: msg.current,
          total: msg.total,
          eta_s: msg.eta_s,
        }
        break
      }

      case 'pipeline_completed': {
        pipelineRunning.value = false
        fetchExperiment(id)
        fetchResults(id)
        fetchExperiments()
        toast.success('Pipeline finished')
        break
      }

      case 'experiment_deleted': {
        if (msg.experiment_id === id) {
          experiment.value = null
          toast.info('Experiment was deleted')
          const router = useRouter()
          router.push('/')
        }
        fetchExperiments()
        break
      }
    }
  })
}

// ---------------------------------------------------------------------------
// Public composable
// ---------------------------------------------------------------------------

export function useExperimentDetail(experimentId: () => string | null) {
  const { send } = useWebSocket()
  const toast = useToast()
  const { fetchExperiments } = useExperiments()

  const anyStepRunning = computed(() => {
    if (!experiment.value) return false
    return experiment.value.steps.some((s) => s.status === 'running')
  })

  // Wire up WebSocket listener once (singleton, never torn down)
  ensureWsSubscription(experimentId)

  // Watch for experiment ID changes — only reset when ID truly changes
  watch(experimentId, async (id) => {
    if (id === currentExperimentId) return // no-op if same experiment
    currentExperimentId = id

    if (id) {
      // Reset transient state for the new experiment
      outputLines.value = {}
      liveMetrics.value = {}
      canvases.value = {}
      progress.value = {}
      results.value = {}
      pipelineRunning.value = false

      await fetchExperiment(id)
      await fetchResults(id)
      await fetchStepCanvases(id)
    } else {
      experiment.value = null
    }
  }, { immediate: true })

  // --- Actions (close over experimentId getter) ---

  async function runStep(stepName: string) {
    const id = experimentId()
    if (!id) return
    outputLines.value[stepName] = []
    liveMetrics.value[stepName] = {}
    delete progress.value[stepName]
    const step = findStep(stepName)
    if (step) step.status = 'running' as StepStatus
    try {
      const res = await fetch(`/api/experiments/${id}/steps/${stepName}/run`, { method: 'POST' })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
    } catch (e) {
      error.value = (e as Error).message
      toast.error(`Failed to run step "${stepName}"`)
      if (step) step.status = 'pending' as StepStatus
    }
  }

  async function stopStep(stepName: string) {
    const id = experimentId()
    if (!id) return
    send({ type: 'interrupt', experiment_id: id, step_name: stepName })
    try {
      await fetch(`/api/experiments/${id}/steps/${stepName}/stop`, { method: 'POST' })
    } catch {
      // best-effort
    }
  }

  async function updateStepCode(stepName: string, code: string) {
    const id = experimentId()
    if (!id) return
    try {
      const res = await fetch(`/api/experiments/${id}/steps/${stepName}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code }),
      })
      if (res.ok) {
        const step = findStep(stepName)
        if (step) step.code = code
      }
    } catch {
      // non-fatal
    }
  }

  async function addStep(name: string, code: string = '') {
    const id = experimentId()
    if (!id) return
    error.value = null
    try {
      const res = await fetch(`/api/experiments/${id}/steps`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, code }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const exp: Experiment = await res.json()
      experiment.value = exp
      toast.success(`Step "${name}" added`)
    } catch (e) {
      error.value = (e as Error).message
      toast.error(`Failed to add step "${name}"`)
    }
  }

  async function deleteStep(stepName: string) {
    const id = experimentId()
    if (!id) return
    error.value = null
    try {
      const res = await fetch(`/api/experiments/${id}/steps/${stepName}`, { method: 'DELETE' })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const exp: Experiment = await res.json()
      experiment.value = exp
    } catch (e) {
      error.value = (e as Error).message
    }
  }

  async function runPipeline() {
    const id = experimentId()
    if (!id) return
    pipelineRunning.value = true
    error.value = null
    try {
      const res = await fetch(`/api/experiments/${id}/run`, { method: 'POST' })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
    } catch (e) {
      error.value = (e as Error).message
      toast.error('Failed to start pipeline')
      pipelineRunning.value = false
    }
  }

  return {
    experiment,
    results,
    canvases,
    outputLines,
    liveMetrics,
    progress,
    loading,
    error,
    anyStepRunning,
    pipelineRunning,
    runStep,
    stopStep,
    updateStepCode,
    addStep,
    deleteStep,
    runPipeline,
    fetchExperiment,
    fetchResults,
    send,
  }
}
