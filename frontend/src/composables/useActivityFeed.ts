import { ref, readonly } from 'vue'
import type { WsMessage } from '../types'
import { useWebSocket } from './useWebSocket'

export interface ActivityEntry {
  id: number
  timestamp: number
  type: string
  experimentId: string
  experimentName: string
  stepName: string
  message: string
  metrics: Record<string, number | string>
}

const MAX_ENTRIES = 100
const feed = ref<ActivityEntry[]>([])
let nextId = 1
let subscribed = false

function formatEventMessage(msg: WsMessage): { message: string; experimentName: string; stepName: string; metrics: Record<string, number | string> } | null {
  switch (msg.type) {
    case 'experiment_created': {
      const exp = (msg as any).experiment
      return {
        message: `Experiment "${exp?.name ?? 'unknown'}" created`,
        experimentName: exp?.name ?? '',
        stepName: '',
        metrics: {},
      }
    }
    case 'step_added': {
      const exp = (msg as any).experiment
      return {
        message: `Step "${msg.step_name}" added`,
        experimentName: exp?.name ?? '',
        stepName: msg.step_name,
        metrics: {},
      }
    }
    case 'step_started': {
      return {
        message: `Step "${msg.step_name}" started`,
        experimentName: '',
        stepName: msg.step_name,
        metrics: {},
      }
    }
    case 'step_completed': {
      const status = msg.status === 'completed' ? 'completed' : 'failed'
      const dur = msg.duration_s != null ? ` (${msg.duration_s.toFixed(1)}s)` : ''
      return {
        message: `Step "${msg.step_name}" ${status}${dur}`,
        experimentName: '',
        stepName: msg.step_name,
        metrics: {},
      }
    }
    case 'step_updated': {
      return {
        message: `Step "${(msg as any).step_name}" updated`,
        experimentName: '',
        stepName: (msg as any).step_name ?? '',
        metrics: {},
      }
    }
    case 'step_deleted': {
      return {
        message: `Step "${(msg as any).step_name}" deleted`,
        experimentName: '',
        stepName: (msg as any).step_name ?? '',
        metrics: {},
      }
    }
    case 'experiment_updated': {
      const exp = (msg as any).experiment
      return {
        message: `Experiment "${exp?.name ?? 'unknown'}" updated`,
        experimentName: exp?.name ?? '',
        stepName: '',
        metrics: {},
      }
    }
    case 'experiment_deleted': {
      return {
        message: `Experiment deleted`,
        experimentName: '',
        stepName: '',
        metrics: {},
      }
    }
    case 'pipeline_completed': {
      return {
        message: `Pipeline finished`,
        experimentName: '',
        stepName: '',
        metrics: {},
      }
    }
    case 'metrics_live': {
      return {
        message: `Metrics update for "${msg.step_name}"`,
        experimentName: '',
        stepName: msg.step_name,
        metrics: msg.data ?? {},
      }
    }
    case 'canvas_update': {
      return {
        message: `Canvas "${msg.canvas_name}" updated for "${msg.step_name}"`,
        experimentName: '',
        stepName: msg.step_name,
        metrics: {},
      }
    }
    default:
      return null
  }
}

function ensureSubscription() {
  if (subscribed) return
  subscribed = true

  const { subscribe } = useWebSocket()
  subscribe((msg: WsMessage) => {
    // Skip noisy events that aren't useful in the feed
    if (msg.type === 'stdout' || msg.type === 'stderr' || msg.type === 'gpu_stats' || msg.type === 'progress' || msg.type === 'exec_result') return

    const formatted = formatEventMessage(msg)
    if (!formatted) return

    const experimentId = 'experiment_id' in msg ? (msg as any).experiment_id : ''

    const entry: ActivityEntry = {
      id: nextId++,
      timestamp: Date.now(),
      type: msg.type,
      experimentId,
      experimentName: formatted.experimentName,
      stepName: formatted.stepName,
      message: formatted.message,
      metrics: formatted.metrics,
    }

    feed.value = [entry, ...feed.value].slice(0, MAX_ENTRIES)
  })
}

export function useActivityFeed() {
  ensureSubscription()
  return {
    feed: readonly(feed),
  }
}
