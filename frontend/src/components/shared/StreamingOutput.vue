<script setup lang="ts">
import { ref, watch, nextTick, onMounted } from 'vue'

const props = defineProps<{
  lines: string[]
}>()

const container = ref<HTMLDivElement | null>(null)
const autoScroll = ref(true)

// ANSI SGR code -> inline style
const ansiMap: Record<string, string> = {
  '0': '',
  '1': 'font-weight:bold',
  '30': 'color:#282828', '31': 'color:#fb4934', '32': 'color:#b8bb26',
  '33': 'color:#fabd2f', '34': 'color:#83a598', '35': 'color:#d3869b',
  '36': 'color:#8ec07c', '37': 'color:#ebdbb2',
  '90': 'color:#928374', '91': 'color:#fb4934', '92': 'color:#b8bb26',
  '93': 'color:#fabd2f', '94': 'color:#83a598', '95': 'color:#d3869b',
  '96': 'color:#8ec07c', '97': 'color:#ebdbb2',
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
      } else if (ansiMap[c]) {
        out += `<span style="${ansiMap[c]}">`
        open++
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
    class="font-mono text-xs leading-5 overflow-y-auto"
    style="
      background: var(--color-bg-hard);
      color: var(--color-fg2);
      max-height: 320px;
      min-height: 32px;
      padding: 6px 8px;
      border-radius: 2px;
    "
    @scroll="onScroll"
  >
    <div v-if="lines.length === 0" style="color: var(--color-fg-dim)">No output yet</div>
    <div v-for="(line, i) in lines" :key="i" v-html="parseAnsi(line)" />
  </div>
</template>
