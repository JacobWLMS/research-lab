import { ref, readonly } from 'vue'
import type { WsMessage } from '../types'

type WsCallback = (msg: WsMessage) => void

// Singleton state -- shared across all consumers
const connected = ref(false)
let ws: WebSocket | null = null
let reconnectTimer: ReturnType<typeof setTimeout> | null = null
let reconnectAttempt = 0
const MAX_RECONNECT_DELAY = 10_000
const BASE_DELAY = 500
const listeners = new Set<WsCallback>()

// Track connection-loss and restoration for notifications
let wasConnected = false
const connectionCallbacks = new Set<(state: 'connected' | 'disconnected') => void>()

function getWsUrl(): string {
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${proto}//${location.host}/api/ws`
}

function connect() {
  if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
    return
  }

  try {
    ws = new WebSocket(getWsUrl())
  } catch {
    scheduleReconnect()
    return
  }

  ws.onopen = () => {
    connected.value = true
    reconnectAttempt = 0
    if (wasConnected) {
      // Reconnected after a drop
      for (const cb of connectionCallbacks) cb('connected')
    }
    wasConnected = true
  }

  ws.onclose = () => {
    const wasOpen = connected.value
    connected.value = false
    ws = null
    if (wasOpen) {
      for (const cb of connectionCallbacks) cb('disconnected')
    }
    scheduleReconnect()
  }

  ws.onerror = () => {
    // onclose fires after onerror -- reconnect handled there
  }

  ws.onmessage = (event: MessageEvent) => {
    try {
      const msg = JSON.parse(event.data) as WsMessage
      for (const cb of listeners) {
        try {
          cb(msg)
        } catch {
          // don't let one bad listener break others
        }
      }
    } catch {
      // ignore malformed messages
    }
  }
}

function scheduleReconnect() {
  if (reconnectTimer) return
  const delay = Math.min(BASE_DELAY * 2 ** reconnectAttempt, MAX_RECONNECT_DELAY)
  reconnectAttempt++
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null
    connect()
  }, delay)
}

function send(data: Record<string, unknown>) {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(data))
  }
}

function subscribe(cb: WsCallback): () => void {
  listeners.add(cb)
  // auto-connect on first subscription
  if (!ws) connect()
  return () => {
    listeners.delete(cb)
  }
}

function onConnectionChange(cb: (state: 'connected' | 'disconnected') => void): () => void {
  connectionCallbacks.add(cb)
  return () => {
    connectionCallbacks.delete(cb)
  }
}

function disconnect() {
  if (reconnectTimer) {
    clearTimeout(reconnectTimer)
    reconnectTimer = null
  }
  if (ws) {
    ws.onclose = null
    ws.close()
    ws = null
  }
  connected.value = false
}

export function useWebSocket() {
  return {
    connected: readonly(connected),
    connect,
    disconnect,
    send,
    subscribe,
    onConnectionChange,
  }
}
