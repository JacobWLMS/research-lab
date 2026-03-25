import { ref, onUnmounted } from 'vue'
import type { GpuInfo, WsMessage } from '../types'
import { useWebSocket } from './useWebSocket'

export function useGpuStats() {
  const gpu = ref<GpuInfo | null>(null)

  const { subscribe } = useWebSocket()

  const unsubscribe = subscribe((msg: WsMessage) => {
    if (msg.type === 'gpu_stats') {
      gpu.value = {
        name: msg.name ?? gpu.value?.name ?? 'GPU',
        utilization_pct: msg.utilization_pct,
        memory_used_gb: msg.memory_used_gb,
        memory_total_gb: msg.memory_total_gb,
        temperature_c: msg.temperature_c,
      }
    }
  })

  onUnmounted(() => {
    unsubscribe()
  })

  return { gpu }
}
