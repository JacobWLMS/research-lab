// ---------------------------------------------------------------------------
// Core data models (mirrors backend Pydantic schemas)
// ---------------------------------------------------------------------------

export type StepStatus = 'pending' | 'running' | 'completed' | 'failed'
export type KernelStatus = 'idle' | 'busy' | 'dead' | 'not_connected'

export interface Step {
  name: string
  code: string
  depends_on: string[]
  config: Record<string, unknown>
  status: StepStatus
}

export interface Experiment {
  id: string
  name: string
  created_at: string
  updated_at: string
  compute_backend: string
  steps: Step[]
}

export interface ImageOutput {
  label: string
  mime: string
  data: string // base64
}

export interface StepResult {
  step_name: string
  run_number: number
  status: 'completed' | 'failed'
  started_at: string
  completed_at: string
  execution_time_s: number
  stdout: string
  stderr: string
  error: string | null
  images: ImageOutput[]
  metrics: Record<string, number | string>
  structured_data: Record<string, unknown>
}

export interface GpuInfo {
  name: string
  utilization_pct: number
  memory_used_gb: number
  memory_total_gb: number
  temperature_c: number
}

export interface StatusResponse {
  server_running: boolean
  kernel_status: KernelStatus
  gpu: GpuInfo | null
  active_tasks: string[]
  current_experiment: string | null
}

// ---------------------------------------------------------------------------
// Widget types (for AI-composed canvases)
// ---------------------------------------------------------------------------

export interface ChartWidget {
  kind: 'chart'
  title: string
  plotly_json: Record<string, unknown>
}

export interface MetricsWidget {
  kind: 'metrics'
  data: Record<string, number | string>
}

export interface TextWidget {
  kind: 'text'
  content: string
}

export interface ImageWidgetData {
  kind: 'image'
  title: string
  mime: string
  data: string // base64
}

export type CanvasWidget = ChartWidget | MetricsWidget | TextWidget | ImageWidgetData

export interface CanvasData {
  name: string
  widgets: CanvasWidget[]
}

// ---------------------------------------------------------------------------
// WebSocket message types (server -> client)
// ---------------------------------------------------------------------------

export interface WsStepStarted {
  type: 'step_started'
  experiment_id: string
  step_name: string
}

export interface WsStdout {
  type: 'stdout'
  experiment_id: string
  step_name: string
  text: string
}

export interface WsStderr {
  type: 'stderr'
  experiment_id: string
  step_name: string
  text: string
}

export interface WsStepCompleted {
  type: 'step_completed'
  experiment_id: string
  step_name: string
  status: 'completed' | 'failed'
  duration_s: number
}

export interface WsMetricsLive {
  type: 'metrics_live'
  experiment_id: string
  step_name: string
  data: Record<string, number | string>
}

export interface WsCanvasUpdate {
  type: 'canvas_update'
  experiment_id: string
  step_name: string
  canvas_name: string
  widgets: CanvasWidget[]
}

export interface WsGpuStats {
  type: 'gpu_stats'
  name?: string
  utilization_pct: number
  memory_used_gb: number
  memory_total_gb: number
  temperature_c: number
}

export interface WsProgress {
  type: 'progress'
  experiment_id: string
  step_name: string
  current: number
  total: number
  eta_s?: number
}

export interface WsPipelineCompleted {
  type: 'pipeline_completed'
  experiment_id: string
  status?: string
}

export interface WsExecResult {
  type: 'exec_result'
  success: boolean
  stdout: string
  stderr: string
  error: string | null
  images: ImageOutput[]
  result: string | null
}

export interface WsExperimentCreated {
  type: 'experiment_created'
  experiment: Experiment
}

export interface WsStepAdded {
  type: 'step_added'
  experiment_id: string
  step_name: string
  experiment: Experiment
}

export interface WsExperimentDeleted {
  type: 'experiment_deleted'
  experiment_id: string
}

export type WsMessage =
  | WsStepStarted
  | WsStdout
  | WsStderr
  | WsStepCompleted
  | WsMetricsLive
  | WsCanvasUpdate
  | WsGpuStats
  | WsProgress
  | WsPipelineCompleted
  | WsExecResult
  | WsExperimentCreated
  | WsStepAdded
  | WsExperimentDeleted

// ---------------------------------------------------------------------------
// API response helpers
// ---------------------------------------------------------------------------

export interface ExecResult {
  success: boolean
  stdout: string
  stderr: string
  error: string | null
  images: ImageOutput[]
  result: string | null
}

// ---------------------------------------------------------------------------
// Terminal / REPL types
// ---------------------------------------------------------------------------

export interface TerminalEntry {
  id: number
  code: string
  stdout: string
  stderr: string
  error: string | null
  images: ImageOutput[]
  result: string | null
  timestamp: number
}

// ---------------------------------------------------------------------------
// Asset library types
// ---------------------------------------------------------------------------

export interface AssetImage {
  step_name: string
  source: 'canvas' | 'result' | 'artifact'
  canvas_name: string | null
  title: string
  mime: string
  data: string // base64
  index: number
}

export interface AssetArtifact {
  step_name: string
  name: string
  format: string
  path: string
  size_bytes: number
}

export interface AssetsResponse {
  images: AssetImage[]
  artifacts: AssetArtifact[]
}

// ---------------------------------------------------------------------------
// Sort config for experiment list
// ---------------------------------------------------------------------------

export type SortField = 'name' | 'updated_at' | 'created_at' | 'status'

// ---------------------------------------------------------------------------
// Toast notification types
// ---------------------------------------------------------------------------

export type ToastType = 'success' | 'error' | 'info'

export interface Toast {
  id: number
  type: ToastType
  message: string
  duration: number
}

// ---------------------------------------------------------------------------
// Theme
// ---------------------------------------------------------------------------

export type ThemeMode = 'light' | 'dark'
