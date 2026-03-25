<script setup lang="ts">
import { ref, onMounted, watch, onUnmounted } from 'vue'
import { useTheme } from '../../composables/useTheme'

const props = defineProps<{
  plotlyJson: Record<string, unknown>
  title?: string
}>()

const { theme } = useTheme()
const container = ref<HTMLDivElement | null>(null)
let Plotly: typeof import('plotly.js-dist-min') | null = null

function getLayout(): Record<string, unknown> {
  return {
    paper_bgcolor: 'var(--c-plot-paper)',
    plot_bgcolor: 'var(--c-plot-bg)',
    font: { color: 'var(--c-plot-font)', family: 'Inter, system-ui, sans-serif', size: 12 },
    xaxis: { gridcolor: 'var(--c-plot-grid)', zerolinecolor: 'var(--c-plot-zeroline)', color: 'var(--c-plot-axis)' },
    yaxis: { gridcolor: 'var(--c-plot-grid)', zerolinecolor: 'var(--c-plot-zeroline)', color: 'var(--c-plot-axis)' },
    colorway: ['#83a598', '#b8bb26', '#fabd2f', '#fb4934', '#d3869b', '#fe8019', '#458588'],
    margin: { t: 32, r: 16, b: 40, l: 48 },
    legend: { bgcolor: 'transparent', font: { color: 'var(--c-plot-axis)', size: 11 } },
  }
}

const plotConfig: Record<string, unknown> = {
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
  const baseLayout = getLayout()

  // Deep merge axis styles
  const layout: Record<string, unknown> = { ...baseLayout, ...userLayout }
  if (userLayout.xaxis && typeof userLayout.xaxis === 'object') {
    layout.xaxis = { ...(baseLayout.xaxis as Record<string, unknown>), ...(userLayout.xaxis as Record<string, unknown>) }
  }
  if (userLayout.yaxis && typeof userLayout.yaxis === 'object') {
    layout.yaxis = { ...(baseLayout.yaxis as Record<string, unknown>), ...(userLayout.yaxis as Record<string, unknown>) }
  }

  await Plotly.newPlot(container.value, data as any[], layout as any, plotConfig as any)
}

onMounted(render)
watch(() => props.plotlyJson, render, { deep: true })
// Re-render on theme change
watch(theme, () => {
  // Small delay for CSS vars to update
  setTimeout(render, 50)
})

onUnmounted(() => {
  if (container.value && Plotly) {
    Plotly.purge(container.value)
  }
})
</script>

<template>
  <div>
    <div v-if="title" class="plotly-chart__title">{{ title }}</div>
    <div ref="container" class="plotly-chart__container" />
  </div>
</template>

<style scoped>
.plotly-chart__title {
  font-size: 0.75rem;
  font-weight: 500;
  color: var(--c-fg-muted);
  margin-bottom: 0.25rem;
}

.plotly-chart__container {
  width: 100%;
  overflow: hidden;
  min-height: 17.5rem;
  background: var(--c-bg-hard);
  border-radius: var(--radius-sm);
}
</style>
