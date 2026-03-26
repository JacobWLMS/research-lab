import { ref, readonly } from 'vue'
import type { StepStatus } from '../types'

// Shared singleton state for toolbar experiment context.
// ExperimentDetail writes; AppShell reads.

const experimentName = ref<string | null>(null)
const experimentStatus = ref<StepStatus | string>('pending')
const pipelineRunning = ref(false)
const runAllDisabled = ref(false)

// Callbacks -- set by ExperimentDetail, invoked by AppShell toolbar buttons
let _onRunPipeline: (() => void) | null = null
let _onAddStep: (() => void) | null = null
let _onRefreshDetail: (() => void) | null = null

function setContext(opts: {
  name: string | null
  status: StepStatus | string
  pipelineRunning: boolean
  runAllDisabled: boolean
  onRunPipeline: (() => void) | null
  onAddStep: (() => void) | null
  onRefreshDetail?: (() => void) | null
}) {
  experimentName.value = opts.name
  experimentStatus.value = opts.status
  pipelineRunning.value = opts.pipelineRunning
  runAllDisabled.value = opts.runAllDisabled
  _onRunPipeline = opts.onRunPipeline
  _onAddStep = opts.onAddStep
  _onRefreshDetail = opts.onRefreshDetail ?? null
}

function clearContext() {
  experimentName.value = null
  experimentStatus.value = 'pending'
  pipelineRunning.value = false
  runAllDisabled.value = false
  _onRunPipeline = null
  _onAddStep = null
  _onRefreshDetail = null
}

function triggerRunPipeline() {
  _onRunPipeline?.()
}

function triggerAddStep() {
  _onAddStep?.()
}

function triggerRefreshDetail() {
  _onRefreshDetail?.()
}

export function useToolbarContext() {
  return {
    experimentName: readonly(experimentName),
    experimentStatus: readonly(experimentStatus),
    pipelineRunning: readonly(pipelineRunning),
    runAllDisabled: readonly(runAllDisabled),
    setContext,
    clearContext,
    triggerRunPipeline,
    triggerAddStep,
    triggerRefreshDetail,
  }
}
