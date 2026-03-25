<script setup lang="ts">
import { ref, onMounted, watch, shallowRef, onUnmounted } from 'vue'
import { useTheme } from '../../composables/useTheme'

const props = withDefaults(defineProps<{
  code: string
  editable?: boolean
}>(), {
  editable: false,
})

const emit = defineEmits<{
  'update:code': [code: string]
}>()

const { theme } = useTheme()
const container = ref<HTMLDivElement | null>(null)
const editorView = shallowRef<import('@codemirror/view').EditorView | null>(null)
let loaded = false

async function initEditor() {
  if (!container.value || loaded) return
  loaded = true

  const [
    { EditorView, lineNumbers },
    { EditorState },
    { python },
    { oneDark },
  ] = await Promise.all([
    import('@codemirror/view'),
    import('@codemirror/state'),
    import('@codemirror/lang-python'),
    import('@codemirror/theme-one-dark'),
  ])

  const gruvboxTheme = EditorView.theme({
    '&': {
      backgroundColor: 'var(--c-cm-bg)',
      color: 'var(--c-fg)',
      fontSize: '0.8125rem',
      fontFamily: 'var(--font-mono)',
    },
    '.cm-gutters': {
      backgroundColor: 'var(--c-cm-gutter)',
      color: 'var(--c-cm-gutter-fg)',
      border: 'none',
    },
    '.cm-activeLineGutter': {
      backgroundColor: 'var(--c-cm-active-line)',
    },
    '.cm-activeLine': {
      backgroundColor: 'var(--c-cm-active-line)',
    },
    '&.cm-focused .cm-cursor': {
      borderLeftColor: 'var(--c-cm-cursor)',
    },
    '&.cm-focused .cm-selectionBackground, .cm-selectionBackground': {
      backgroundColor: 'var(--c-cm-selection)',
    },
    '.cm-line': {
      padding: '0 4px',
    },
  })

  const extensions = [
    python(),
    oneDark,
    gruvboxTheme,
    lineNumbers(),
    EditorView.lineWrapping,
    EditorState.readOnly.of(!props.editable),
  ]

  if (props.editable) {
    extensions.push(
      EditorView.updateListener.of((update) => {
        if (update.docChanged) {
          emit('update:code', update.state.doc.toString())
        }
      })
    )
  }

  const state = EditorState.create({
    doc: props.code,
    extensions,
  })

  editorView.value = new EditorView({
    state,
    parent: container.value,
  })
}

watch(() => props.code, (newCode) => {
  const view = editorView.value
  if (!view) return
  const current = view.state.doc.toString()
  if (newCode !== current) {
    view.dispatch({
      changes: { from: 0, to: view.state.doc.length, insert: newCode },
    })
  }
})

onMounted(initEditor)

onUnmounted(() => {
  editorView.value?.destroy()
})
</script>

<template>
  <div
    ref="container"
    class="code-block"
  />
</template>

<style scoped>
.code-block {
  overflow: hidden;
  min-height: 3rem;
  background: var(--c-cm-bg);
  border-radius: var(--radius-sm);
}
</style>
