<script setup lang="ts">
import { ref, watch, nextTick, onMounted } from 'vue'

const props = defineProps<{
  lines: string[]
}>()

const container = ref<HTMLDivElement | null>(null)
const autoScroll = ref(true)

// ANSI SGR code -> inline style (theme-aware)
function ansiStyle(code: string): string {
  switch (code) {
    case '1': return 'font-weight:bold'
    case '30': return 'color:var(--c-bg)';    case '31': return 'color:var(--c-red)'
    case '32': return 'color:var(--c-green)';  case '33': return 'color:var(--c-yellow)'
    case '34': return 'color:var(--c-aqua)';   case '35': return 'color:var(--c-purple)'
    case '36': return 'color:var(--c-aqua)';   case '37': return 'color:var(--c-fg)'
    case '90': return 'color:var(--c-fg-dim)'; case '91': return 'color:var(--c-red)'
    case '92': return 'color:var(--c-green)';  case '93': return 'color:var(--c-yellow)'
    case '94': return 'color:var(--c-aqua)';   case '95': return 'color:var(--c-purple)'
    case '96': return 'color:var(--c-aqua)';   case '97': return 'color:var(--c-fg)'
    default: return ''
  }
}

function esc(t: string): string {
  return t.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

function parseAnsi(text: string): string {
  // eslint-disable-next-line no-control-regex
  const re = /\x1b\[([0-9;]*)m/g
  let out = ''
  let last = 0
  let open = 0
  let m: RegExpExecArray | null
  while ((m = re.exec(text)) !== null) {
    out += esc(text.slice(last, m.index))
    last = re.lastIndex
    for (const c of m[1].split(';').filter(Boolean)) {
      if (c === '0') {
        while (open > 0) { out += '</span>'; open-- }
      } else {
        const style = ansiStyle(c)
        if (style) {
          out += `<span style="${style}">`
          open++
        }
      }
    }
  }
  out += esc(text.slice(last))
  while (open > 0) { out += '</span>'; open-- }
  return out
}

function scrollToBottom() {
  if (!autoScroll.value || !container.value) return
  container.value.scrollTop = container.value.scrollHeight
}

function onScroll() {
  if (!container.value) return
  const { scrollTop, scrollHeight, clientHeight } = container.value
  autoScroll.value = scrollHeight - scrollTop - clientHeight < 32
}

watch(() => props.lines.length, () => nextTick(scrollToBottom))
onMounted(scrollToBottom)
</script>

<template>
  <div
    ref="container"
    class="streaming-output"
    @scroll="onScroll"
  >
    <div v-if="lines.length === 0" class="streaming-output__empty">No output yet</div>
    <div v-for="(line, i) in lines" :key="i" v-html="parseAnsi(line)" />
  </div>
</template>

<style scoped>
.streaming-output {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  line-height: 1.4rem;
  overflow-y: auto;
  background: var(--c-bg-hard);
  color: var(--c-fg2);
  max-height: 20rem;
  min-height: 2rem;
  padding: 0.375rem 0.5rem;
  border-radius: var(--radius-sm);
}

.streaming-output__empty {
  color: var(--c-fg-dim);
}
</style>
