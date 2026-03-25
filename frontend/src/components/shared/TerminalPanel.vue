<script setup lang="ts">
import { ref, nextTick, watch, onMounted, onUnmounted } from 'vue'
import type { TerminalEntry, ImageOutput, WsMessage } from '../../types'
import { useWebSocket } from '../../composables/useWebSocket'

const inputCode = ref('')
const history = ref<TerminalEntry[]>([])
const running = ref(false)
const entryCounter = ref(0)
const outputContainer = ref<HTMLDivElement | null>(null)
const textareaEl = ref<HTMLTextAreaElement | null>(null)

const { send, subscribe } = useWebSocket()
let pendingEntry: TerminalEntry | null = null

function scrollToBottom() {
  nextTick(() => {
    if (outputContainer.value) {
      outputContainer.value.scrollTop = outputContainer.value.scrollHeight
    }
  })
}

// Listen for exec_result from WebSocket
const unsubscribe = subscribe((msg: WsMessage) => {
  if (msg.type === 'exec_result' && pendingEntry) {
    pendingEntry.stdout = msg.stdout ?? ''
    pendingEntry.stderr = msg.stderr ?? ''
    pendingEntry.error = msg.error ?? null
    pendingEntry.result = msg.result ?? null
    pendingEntry.images = (msg.images ?? []) as ImageOutput[]
    pendingEntry = null
    running.value = false
    scrollToBottom()
  }
  // Also handle streaming adhoc output
  if (msg.type === 'stdout' && 'experiment_id' in msg && msg.experiment_id === '__adhoc__' && pendingEntry) {
    pendingEntry.stdout += msg.text
    scrollToBottom()
  }
  if (msg.type === 'stderr' && 'experiment_id' in msg && msg.experiment_id === '__adhoc__' && pendingEntry) {
    pendingEntry.stderr += msg.text
    scrollToBottom()
  }
})

function executeCode() {
  const code = inputCode.value.trim()
  if (!code || running.value) return

  running.value = true
  const entry: TerminalEntry = {
    id: ++entryCounter.value,
    code,
    stdout: '',
    stderr: '',
    error: null,
    result: null,
    images: [],
    timestamp: Date.now(),
  }
  history.value.push(entry)
  pendingEntry = entry
  inputCode.value = ''
  scrollToBottom()

  // Send via WebSocket for streaming
  send({ type: 'exec', code })

  // Fallback timeout: if WS doesn't respond, use REST
  setTimeout(async () => {
    if (!running.value) return // already completed via WS
    try {
      const res = await fetch('/api/exec', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code }),
      })
      if (res.ok && pendingEntry === entry) {
        const data = await res.json()
        entry.stdout = data.stdout ?? ''
        entry.stderr = data.stderr ?? ''
        entry.error = data.error ?? null
        entry.result = data.result ?? null
        entry.images = (data.images ?? []) as ImageOutput[]
      }
    } catch (e) {
      if (pendingEntry === entry) {
        entry.error = (e as Error).message
      }
    } finally {
      if (pendingEntry === entry) {
        pendingEntry = null
        running.value = false
        scrollToBottom()
      }
    }
  }, 500)
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && e.shiftKey) {
    e.preventDefault()
    executeCode()
  }
}

function autoResize() {
  const el = textareaEl.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 160) + 'px'
}

watch(inputCode, () => nextTick(autoResize))

onMounted(() => {
  textareaEl.value?.focus()
})

onUnmounted(() => {
  unsubscribe()
})
</script>

<template>
  <div class="flex flex-col h-full overflow-hidden" style="background: var(--color-bg-hard)">
    <!-- Header -->
    <div
      class="shrink-0 flex items-center justify-between px-3 py-1.5 border-b"
      style="border-color: var(--color-bg2); background: var(--color-bg)"
    >
      <div class="flex items-center gap-1.5">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="color: var(--color-aqua)">
          <polyline points="4 17 10 11 4 5"/>
          <line x1="12" y1="19" x2="20" y2="19"/>
        </svg>
        <span class="text-xs font-medium" style="color: var(--color-fg-muted)">Terminal</span>
        <span class="text-xs" style="color: var(--color-fg-dim)">(shared kernel)</span>
      </div>
      <div class="flex items-center gap-2">
        <span
          v-if="running"
          class="text-xs flex items-center gap-1"
          style="color: var(--color-yellow)"
        >
          <span class="inline-block w-1.5 h-1.5 rounded-full animate-pulse-glow" style="background: var(--color-yellow)"></span>
          Running
        </span>
        <span class="text-xs font-mono" style="color: var(--color-fg-dim)">
          {{ history.length }} cmd{{ history.length !== 1 ? 's' : '' }}
        </span>
      </div>
    </div>

    <!-- Output history -->
    <div
      ref="outputContainer"
      class="flex-1 overflow-y-auto px-3 py-2 font-mono text-xs leading-5"
      style="color: var(--color-fg2)"
    >
      <!-- Empty state -->
      <div
        v-if="history.length === 0 && !running"
        class="flex flex-col items-center justify-center h-full gap-1"
      >
        <p class="text-xs" style="color: var(--color-fg-dim)">
          Type Python code below and press
          <kbd class="px-1 py-px font-mono" style="background: var(--color-bg1); color: var(--color-fg-muted); border-radius: 2px">Shift+Enter</kbd>
          to run
        </p>
      </div>

      <!-- Entries -->
      <div v-for="entry in history" :key="entry.id" class="mb-3">
        <div class="flex gap-1">
          <span style="color: var(--color-aqua)" class="select-none shrink-0">In [{{ entry.id }}]:</span>
          <pre class="whitespace-pre-wrap break-words flex-1 m-0" style="color: var(--color-fg)">{{ entry.code }}</pre>
        </div>
        <div v-if="entry.stdout" class="mt-0.5 pl-4">
          <pre class="whitespace-pre-wrap break-words m-0" style="color: var(--color-fg2)">{{ entry.stdout }}</pre>
        </div>
        <div v-if="entry.result" class="mt-0.5 pl-4">
          <pre class="whitespace-pre-wrap break-words m-0" style="color: var(--color-fg-muted)">{{ entry.result }}</pre>
        </div>
        <div v-if="entry.stderr" class="mt-0.5 pl-4">
          <pre class="whitespace-pre-wrap break-words m-0" style="color: var(--color-yellow)">{{ entry.stderr }}</pre>
        </div>
        <div v-if="entry.error" class="mt-0.5 pl-4">
          <pre class="whitespace-pre-wrap break-words m-0" style="color: var(--color-red)">{{ entry.error }}</pre>
        </div>
        <div
          v-if="entry.images.length > 0"
          class="mt-1 pl-4 flex flex-wrap gap-2"
        >
          <img
            v-for="(img, idx) in entry.images"
            :key="idx"
            :src="`data:${img.mime};base64,${img.data}`"
            :alt="img.label || 'Output'"
            class="max-w-[400px] max-h-[300px]"
            style="border: 1px solid var(--color-bg2); border-radius: 2px"
          />
        </div>
      </div>

      <!-- Running dots -->
      <div v-if="running" class="flex items-center gap-1 pl-1">
        <span style="color: var(--color-aqua)" class="select-none">In [{{ entryCounter + 1 }}]:</span>
        <span class="inline-flex gap-0.5" style="color: var(--color-fg-dim)">
          <span class="animate-pulse-glow">.</span>
          <span class="animate-pulse-glow" style="animation-delay: 0.2s">.</span>
          <span class="animate-pulse-glow" style="animation-delay: 0.4s">.</span>
        </span>
      </div>
    </div>

    <!-- Input area -->
    <div
      class="shrink-0 border-t flex items-end gap-2 px-3 py-2"
      style="border-color: var(--color-bg2); background: var(--color-bg)"
    >
      <span class="text-xs font-mono shrink-0 py-1" style="color: var(--color-aqua)">
        In [{{ entryCounter + 1 }}]:
      </span>
      <textarea
        ref="textareaEl"
        v-model="inputCode"
        class="flex-1 resize-none font-mono text-xs leading-5 px-2 py-1 border-none outline-none"
        style="background: var(--color-bg-hard); color: var(--color-fg); min-height: 28px; max-height: 160px; border-radius: 2px"
        placeholder="Enter Python code..."
        rows="1"
        :disabled="running"
        @keydown="onKeydown"
      />
      <button
        class="shrink-0 flex items-center gap-1 px-3 py-1 text-xs font-medium cursor-pointer"
        :style="{
          background: running || !inputCode.trim() ? 'var(--color-bg2)' : 'var(--color-aqua)',
          color: running || !inputCode.trim() ? 'var(--color-fg-dim)' : 'var(--color-bg-hard)',
          opacity: running || !inputCode.trim() ? 0.5 : 1,
          cursor: running || !inputCode.trim() ? 'not-allowed' : 'pointer',
          borderRadius: '2px',
        }"
        :disabled="running || !inputCode.trim()"
        @click="executeCode"
      >
        <svg
          v-if="running"
          class="animate-spin h-3 w-3"
          viewBox="0 0 24 24"
          fill="none"
        >
          <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="2.5" opacity="0.3"/>
          <path d="M4 12a8 8 0 018-8" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"/>
        </svg>
        <template v-else>Run</template>
      </button>
    </div>
  </div>
</template>
