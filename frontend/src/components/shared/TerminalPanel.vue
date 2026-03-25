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
const cmdHistory = ref<string[]>([])
const cmdHistoryIdx = ref(-1)

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
  cmdHistory.value.push(code)
  cmdHistoryIdx.value = cmdHistory.value.length
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
    return
  }
  // Command history navigation
  if (e.key === 'ArrowUp' && cmdHistory.value.length > 0) {
    e.preventDefault()
    if (cmdHistoryIdx.value > 0) {
      cmdHistoryIdx.value--
      inputCode.value = cmdHistory.value[cmdHistoryIdx.value]
    }
    return
  }
  if (e.key === 'ArrowDown' && cmdHistory.value.length > 0) {
    e.preventDefault()
    if (cmdHistoryIdx.value < cmdHistory.value.length - 1) {
      cmdHistoryIdx.value++
      inputCode.value = cmdHistory.value[cmdHistoryIdx.value]
    } else {
      cmdHistoryIdx.value = cmdHistory.value.length
      inputCode.value = ''
    }
    return
  }
}

function clearHistory() {
  history.value = []
  entryCounter.value = 0
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
  <div class="terminal">
    <!-- Header -->
    <div class="terminal__header">
      <div class="terminal__header-left">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="color: var(--c-aqua)">
          <polyline points="4 17 10 11 4 5"/>
          <line x1="12" y1="19" x2="20" y2="19"/>
        </svg>
        <span class="terminal__title">Terminal</span>
        <span class="terminal__subtitle">(shared kernel)</span>
      </div>
      <div class="terminal__header-right">
        <span v-if="running" class="terminal__running-indicator">
          <span class="terminal__running-dot animate-pulse-glow" />
          Running
        </span>
        <button
          class="terminal__clear-btn"
          title="Clear terminal history"
          @click="clearHistory"
        >
          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M18 6L6 18M6 6l12 12" stroke-linecap="round"/>
          </svg>
          Clear
        </button>
        <span class="terminal__cmd-count">{{ history.length }} cmd{{ history.length !== 1 ? 's' : '' }}</span>
      </div>
    </div>

    <!-- Output history -->
    <div ref="outputContainer" class="terminal__output">
      <!-- Empty state -->
      <div v-if="history.length === 0 && !running" class="terminal__empty">
        <p>
          Type Python code below and press
          <kbd class="terminal__kbd">Shift+Enter</kbd>
          to run.
          <kbd class="terminal__kbd">&uarr;</kbd>/<kbd class="terminal__kbd">&darr;</kbd> for history.
        </p>
      </div>

      <!-- Entries -->
      <div v-for="entry in history" :key="entry.id" class="terminal__entry">
        <div class="terminal__entry-prompt">
          <span class="terminal__prompt-label">In [{{ entry.id }}]:</span>
          <pre class="terminal__entry-code">{{ entry.code }}</pre>
        </div>
        <div v-if="entry.stdout" class="terminal__entry-output">
          <pre class="terminal__entry-text" style="color: var(--c-fg2)">{{ entry.stdout }}</pre>
        </div>
        <div v-if="entry.result" class="terminal__entry-output">
          <pre class="terminal__entry-text" style="color: var(--c-fg-muted)">{{ entry.result }}</pre>
        </div>
        <div v-if="entry.stderr" class="terminal__entry-output">
          <pre class="terminal__entry-text" style="color: var(--c-yellow)">{{ entry.stderr }}</pre>
        </div>
        <div v-if="entry.error" class="terminal__entry-output">
          <pre class="terminal__entry-text" style="color: var(--c-red)">{{ entry.error }}</pre>
        </div>
        <div v-if="entry.images.length > 0" class="terminal__entry-images">
          <img
            v-for="(img, idx) in entry.images"
            :key="idx"
            :src="`data:${img.mime};base64,${img.data}`"
            :alt="img.label || 'Output'"
            class="terminal__entry-image"
          />
        </div>
      </div>

      <!-- Running dots -->
      <div v-if="running" class="terminal__running-dots">
        <span class="terminal__prompt-label">In [{{ entryCounter + 1 }}]:</span>
        <span class="terminal__dots">
          <span class="animate-pulse-glow">.</span>
          <span class="animate-pulse-glow" style="animation-delay: 0.2s">.</span>
          <span class="animate-pulse-glow" style="animation-delay: 0.4s">.</span>
        </span>
      </div>
    </div>

    <!-- Input area -->
    <div class="terminal__input">
      <span class="terminal__input-prompt">In [{{ entryCounter + 1 }}]:</span>
      <textarea
        ref="textareaEl"
        v-model="inputCode"
        class="terminal__textarea"
        placeholder="Enter Python code..."
        rows="1"
        :disabled="running"
        @keydown="onKeydown"
      />
      <button
        class="terminal__submit-btn"
        :disabled="running || !inputCode.trim()"
        @click="executeCode"
      >
        <svg
          v-if="running"
          class="animate-spin"
          width="12"
          height="12"
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

<style scoped>
.terminal {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
  background: var(--c-bg-hard);
}

/* Header */
.terminal__header {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.375rem 0.75rem;
  border-bottom: 1px solid var(--c-border);
  background: var(--c-surface);
}

.terminal__header-left {
  display: flex;
  align-items: center;
  gap: 0.375rem;
}

.terminal__header-right {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.terminal__title {
  font-size: 0.75rem;
  font-weight: 500;
  color: var(--c-fg-muted);
}

.terminal__subtitle {
  font-size: 0.75rem;
  color: var(--c-fg-dim);
}

.terminal__running-indicator {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  font-size: 0.75rem;
  color: var(--c-yellow);
}

.terminal__running-dot {
  display: inline-block;
  width: 0.375rem;
  height: 0.375rem;
  border-radius: 50%;
  background: var(--c-yellow);
}

.terminal__clear-btn {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  font-size: 0.6875rem;
  padding: 0.125rem 0.375rem;
  color: var(--c-fg-dim);
  background: transparent;
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: background 0.12s, color 0.12s;
}

.terminal__clear-btn:hover {
  background: var(--c-surface-hover);
  color: var(--c-fg-muted);
}

.terminal__cmd-count {
  font-size: 0.6875rem;
  font-family: var(--font-mono);
  color: var(--c-fg-dim);
}

/* Output */
.terminal__output {
  flex: 1;
  overflow-y: auto;
  padding: 0.5rem 0.75rem;
  font-family: var(--font-mono);
  font-size: 0.75rem;
  line-height: 1.4rem;
  color: var(--c-fg2);
}

.terminal__empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--c-fg-dim);
  font-size: 0.75rem;
}

.terminal__kbd {
  display: inline-block;
  padding: 0 0.25rem;
  font-family: var(--font-mono);
  font-size: 0.6875rem;
  background: var(--c-bg1);
  color: var(--c-fg-muted);
  border-radius: var(--radius-sm);
}

.terminal__entry {
  margin-bottom: 0.75rem;
}

.terminal__entry-prompt {
  display: flex;
  gap: 0.25rem;
}

.terminal__prompt-label {
  color: var(--c-aqua);
  user-select: none;
  flex-shrink: 0;
}

.terminal__entry-code {
  white-space: pre-wrap;
  word-break: break-word;
  flex: 1;
  margin: 0;
  color: var(--c-fg);
}

.terminal__entry-output {
  margin-top: 0.125rem;
  padding-left: 1rem;
}

.terminal__entry-text {
  white-space: pre-wrap;
  word-break: break-word;
  margin: 0;
}

.terminal__entry-images {
  margin-top: 0.25rem;
  padding-left: 1rem;
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.terminal__entry-image {
  max-width: 25rem;
  max-height: 18.75rem;
  border: 1px solid var(--c-border);
  border-radius: var(--radius-sm);
}

.terminal__running-dots {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  padding-left: 0.25rem;
}

.terminal__dots {
  display: inline-flex;
  gap: 0.125rem;
  color: var(--c-fg-dim);
}

/* Input area */
.terminal__input {
  flex-shrink: 0;
  display: flex;
  align-items: flex-end;
  gap: 0.5rem;
  padding: 0.5rem 0.75rem;
  border-top: 1px solid var(--c-border);
  background: var(--c-surface);
}

.terminal__input-prompt {
  font-size: 0.75rem;
  font-family: var(--font-mono);
  color: var(--c-aqua);
  flex-shrink: 0;
  padding: 0.25rem 0;
}

.terminal__textarea {
  flex: 1;
  resize: none;
  font-family: var(--font-mono);
  font-size: 0.75rem;
  line-height: 1.4rem;
  padding: 0.25rem 0.5rem;
  background: var(--c-bg-hard);
  color: var(--c-fg);
  border: none;
  outline: none;
  border-radius: var(--radius-sm);
  min-height: 1.75rem;
  max-height: 10rem;
}

.terminal__submit-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.25rem;
  flex-shrink: 0;
  padding: 0.25rem 0.75rem;
  font-size: 0.75rem;
  font-weight: 500;
  background: var(--c-aqua);
  color: var(--c-bg-hard);
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: opacity 0.12s;
  min-height: 1.75rem;
}

.terminal__submit-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
</style>
