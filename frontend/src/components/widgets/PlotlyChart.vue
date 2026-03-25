<script setup lang="ts">
import { ref, onMounted, watch, onUnmounted } from 'vue'

const props = defineProps<{
  plotlyJson: Record<string, unknown>
  title?: string
}>()

const container = ref<HTMLDivElement | null>(null)
let Plotly: typeof import('plotly.js-dist-min') | null = null

const gruvboxLayout: Record<string, unknown> = {
  paper_bgcolor: '#282828',
  plot_bgcolor: '#1d2021',
  font: { color: '#ebdbb2', family: 'Inter, system-ui, sans-serif', size: 12 },
  xaxis: { gridcolor: '#3c3836', zerolinecolor: '#504945', color: '#a89984' },
  yaxis: { gridcolor: '#3c3836', zerolinecolor: '#504945', color: '#a89984' },
  colorway: ['#83a598', '#b8bb26', '#fabd2f', '#fb4934', '#d3869b', '#fe8019', '#458588'],
  margin: { t: 32, r: 16, b: 40, l: 48 },
  legend: { bgcolor: 'transparent', font: { color: '#a89984', size: 11 } },
}

const gruvboxConfig: Record<string, unknown> = {
  displayModeBar: true,
  modeBarButtonsToRemove: ['lasso2d', 'select2d'],
  responsive: true,
  displaylogo: false,
}

async function render() {
  if (!container.value) return
  if (!Plotly) {
    Plotly = await import('plotly.js-dist-min')
  }

  const data = (props.plotlyJson.data ?? []) as Record<string, unknown>[]
  const userLayout = (props.plotlyJson.layout ?? {}) as Record<string, unknown>

  // Deep merge axis styles
  const layout: Record<string, unknown> = { ...gruvboxLayout, ...userLayout }
  if (userLayout.xaxis && typeof userLayout.xaxis === 'object') {
    layout.xaxis = { ...(gruvboxLayout.xaxis as Record<string, unknown>), ...(userLayout.xaxis as Record<string, unknown>) }
  }
  if (userLayout.yaxis && typeof userLayout.yaxis === 'object') {
    layout.yaxis = { ...(gruvboxLayout.yaxis as Record<string, unknown>), ...(userLayout.yaxis as Record<string, unknown>) }
  }

  await Plotly.newPlot(container.value, data as any[], layout as any, gruvboxConfig as any)
}

onMounted(render)
watch(() => props.plotlyJson, render, { deep: true })

onUnmounted(() => {
  if (container.value && Plotly) {
    Plotly.purge(container.value)
  }
})
</script>

<template>
  <div>
    <div v-if="title" class="text-xs font-medium mb-1" style="color: var(--color-fg-muted)">
      {{ title }}
    </div>
    <div
      ref="container"
      class="w-full overflow-hidden"
      style="min-height: 280px; background: var(--color-bg-hard); border-radius: 2px"
    />
  </div>
</template>
