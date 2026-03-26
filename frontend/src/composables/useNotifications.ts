import { ref, readonly, computed } from 'vue'
import type { WsMessage } from '../types'
import { useWebSocket } from './useWebSocket'

export interface Notification {
  id: number
  timestamp: number
  type: string
  experimentId: string
  stepName: string
  message: string
  read: boolean
}

const MAX_NOTIFICATIONS = 50
const notifications = ref<Notification[]>([])
let nextId = 1
let subscribed = false

function isImportantEvent(type: string): boolean {
  return (
    type === 'step_completed' ||
    type === 'pipeline_completed' ||
    type === 'canvas_update' ||
    type === 'experiment_created'
  )
}

function formatNotification(msg: WsMessage): { message: string; stepName: string } | null {
  switch (msg.type) {
    case 'step_completed': {
      const status = msg.status === 'completed' ? 'completed' : 'failed'
      const dur = msg.duration_s != null ? ` (${msg.duration_s.toFixed(1)}s)` : ''
      return {
        message: `Step "${msg.step_name}" ${status}${dur}`,
        stepName: msg.step_name,
      }
    }
    case 'pipeline_completed': {
      return {
        message: 'Pipeline finished',
        stepName: '',
      }
    }
    case 'canvas_update': {
      return {
        message: `Canvas "${msg.canvas_name}" ready for "${msg.step_name}"`,
        stepName: msg.step_name,
      }
    }
    case 'experiment_created': {
      const exp = (msg as any).experiment
      return {
        message: `Experiment "${exp?.name ?? 'unknown'}" created`,
        stepName: '',
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
    if (!isImportantEvent(msg.type)) return

    const formatted = formatNotification(msg)
    if (!formatted) return

    const experimentId = 'experiment_id' in msg ? (msg as any).experiment_id : ''

    const notification: Notification = {
      id: nextId++,
      timestamp: Date.now(),
      type: msg.type,
      experimentId,
      stepName: formatted.stepName,
      message: formatted.message,
      read: false,
    }

    notifications.value = [notification, ...notifications.value].slice(0, MAX_NOTIFICATIONS)
  })
}

function markAsRead(id: number) {
  const n = notifications.value.find(n => n.id === id)
  if (n) n.read = true
}

function markAllAsRead() {
  for (const n of notifications.value) {
    n.read = true
  }
}

function dismiss(id: number) {
  notifications.value = notifications.value.filter(n => n.id !== id)
}

const unreadCount = computed(() => notifications.value.filter(n => !n.read).length)

export function useNotifications() {
  ensureSubscription()
  return {
    notifications: readonly(notifications),
    unreadCount,
    markAsRead,
    markAllAsRead,
    dismiss,
  }
}
