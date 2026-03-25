import { ref, readonly } from 'vue'
import type { Toast, ToastType } from '../types'

const toasts = ref<Toast[]>([])
let nextId = 0

function addToast(type: ToastType, message: string, duration = 4000) {
  const id = ++nextId
  const toast: Toast = { id, type, message, duration }
  toasts.value.push(toast)
  if (duration > 0) {
    setTimeout(() => removeToast(id), duration)
  }
}

function removeToast(id: number) {
  const idx = toasts.value.findIndex((t) => t.id === id)
  if (idx >= 0) {
    toasts.value.splice(idx, 1)
  }
}

function success(message: string, duration?: number) {
  addToast('success', message, duration)
}

function error(message: string, duration?: number) {
  addToast('error', message, duration ?? 6000)
}

function info(message: string, duration?: number) {
  addToast('info', message, duration)
}

export function useToast() {
  return {
    toasts: readonly(toasts),
    addToast,
    removeToast,
    success,
    error,
    info,
  }
}
