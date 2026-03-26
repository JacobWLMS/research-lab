import { ref, watch } from 'vue'
import type {
  RunSummary,
  StepResult,
  CanvasData,
  CanvasWidget,
} from '../types'

/**
 * Composable for browsing per-step run history.
 *
 * Provides a list of run summaries, a selected run number, and the full
 * result + canvases for the selected run.  The latest run is the default.
 */
export function useRunHistory(
  experimentId: () => string | null,
  stepName: () => string,
) {
  const runs = ref<RunSummary[]>([])
  const selectedRun = ref<number | null>(null) // null = latest
  const runResult = ref<StepResult | null>(null)
  const runCanvases = ref<CanvasData[]>([])
  const loadingHistory = ref(false)
  const loadingRun = ref(false)
  const isViewingOldRun = ref(false)

  async function fetchHistory() {
    const id = experimentId()
    const name = stepName()
    if (!id || !name) return
    loadingHistory.value = true
    try {
      const res = await fetch(
        `/api/experiments/${id}/steps/${encodeURIComponent(name)}/history`,
      )
      if (!res.ok) {
        runs.value = []
        return
      }
      const data = await res.json()
      runs.value = data.runs ?? []
    } catch {
      runs.value = []
    } finally {
      loadingHistory.value = false
    }
  }

  async function selectRun(runNumber: number | null) {
    selectedRun.value = runNumber
    const id = experimentId()
    const name = stepName()
    if (!id || !name) return

    if (runNumber === null) {
      // Reset to latest -- caller can use the normal result/canvases
      isViewingOldRun.value = false
      runResult.value = null
      runCanvases.value = []
      return
    }

    // Check if this is the latest run
    const latestRun = runs.value.length > 0 ? runs.value[0].run_number : null
    isViewingOldRun.value = runNumber !== latestRun

    loadingRun.value = true
    try {
      const res = await fetch(
        `/api/experiments/${id}/steps/${encodeURIComponent(name)}/runs/${runNumber}`,
      )
      if (!res.ok) {
        runResult.value = null
        runCanvases.value = []
        return
      }
      const data = await res.json()
      runResult.value = data.result ?? null
      const rawCanvases: Array<{
        canvas_name?: string
        name?: string
        widgets: CanvasWidget[]
      }> = data.canvases ?? []
      runCanvases.value = rawCanvases.map((c) => ({
        name: c.canvas_name ?? c.name ?? 'Canvas',
        widgets: c.widgets ?? [],
      }))
    } catch {
      runResult.value = null
      runCanvases.value = []
    } finally {
      loadingRun.value = false
    }
  }

  function reset() {
    runs.value = []
    selectedRun.value = null
    runResult.value = null
    runCanvases.value = []
    isViewingOldRun.value = false
  }

  return {
    runs,
    selectedRun,
    runResult,
    runCanvases,
    loadingHistory,
    loadingRun,
    isViewingOldRun,
    fetchHistory,
    selectRun,
    reset,
  }
}
