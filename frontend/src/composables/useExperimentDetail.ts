import { ref, computed, watch, onUnmounted } from 'vue'
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

export function useExperimentDetail(experimentId: () => string | null) {
  const experiment = ref<Experiment | null>(null)
  const results = ref<Record<string, StepResult>>({})
  const canvases = ref<Record<string, CanvasData[]>>({})
  const outputLines = ref<Record<string, string[]>>({})
  const liveMetrics = ref<Record<string, Record<string, number | string>>>({})
  const progress = ref<Record<string, { current: number; total: number; eta_s?: number }>>({})
  const loading = ref(false)
  const error = ref<string | null>(null)
  const pipelineRunning = ref(false)

  const { subscribe, send } = useWebSocket()
  const toast = useToast()
  const router = useRouter()
  const { fetchExperiments } = useExperiments()

  const anyStepRunning = computed(() => {
    if (!experiment.value) return false
    return experiment.value.steps.some((s) => s.status === 'running')
  })

  // Helper to find and mutate a step
  function findStep(name: string): Step | undefined {
    return experiment.value?.steps.find((s) => s.name === name)
  }

  async function fetchExperiment(id: string) {
    loading.value = true
    error.value = null
    try {
      const res = await fetch(`/api/experiments/${id}`)
      if (res.status === 404) {
        // Experiment was deleted -- redirect to home
        experiment.value = null
        toast.info('Experiment not found')
        router.push('/')
        return
      }
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      experiment.value = await res.json()
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
      }
    } catch {
      // non-fatal
    }
  }

  async function runStep(stepName: string) {
    const id = experimentId()
    if (!id) return
    // Clear live state for this step
    outputLines.value[stepName] = []
    liveMetrics.value[stepName] = {}
    delete progress.value[stepName]
    // Optimistically set running
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

  // WebSocket handler for live updates
  const unsubscribe = subscribe((msg: WsMessage) => {
    const id = experimentId()
    if (!id) return

    // Filter to current experiment (except gpu_stats which is global)
    if ('experiment_id' in msg && msg.experiment_id !== id) return

    switch (msg.type) {
      case 'step_started': {
        const step = findStep(msg.step_name)
        if (step) step.status = 'running' as StepStatus
        outputLines.value[msg.step_name] = []
        liveMetrics.value[msg.step_name] = {}
        progress.value[msg.step_name] = { current: 0, total: 0 }
        break
      }

      case 'stdout': {
        if (!outputLines.value[msg.step_name]) outputLines.value[msg.step_name] = []
        outputLines.value[msg.step_name].push(msg.text)
        break
      }

      case 'stderr': {
        if (!outputLines.value[msg.step_name]) outputLines.value[msg.step_name] = []
        outputLines.value[msg.step_name].push(msg.text)
        break
      }

      case 'step_completed': {
        const step = findStep(msg.step_name)
        if (step) step.status = msg.status as StepStatus
        fetchResults(id)
        // Also refresh experiment list so sidebar status updates
        fetchExperiments()
        // Toast notification
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
        // Re-fetch full experiment to sync statuses
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
          router.push('/')
        }
        // Also refresh the sidebar experiment list
        fetchExperiments()
        break
      }
    }
  })

  // Watch for experiment ID changes -- reset state
  watch(experimentId, (id) => {
    if (id) {
      outputLines.value = {}
      liveMetrics.value = {}
      canvases.value = {}
      progress.value = {}
      results.value = {}
      pipelineRunning.value = false
      fetchExperiment(id)
      fetchResults(id)
    } else {
      experiment.value = null
    }
  }, { immediate: true })

  onUnmounted(() => {
    unsubscribe()
  })

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
