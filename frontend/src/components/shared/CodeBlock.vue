<script setup lang="ts">
import { ref, onMounted, watch, shallowRef, onUnmounted } from 'vue'

const props = withDefaults(defineProps<{
  code: string
  editable?: boolean
}>(), {
  editable: false,
})

const emit = defineEmits<{
  'update:code': [code: string]
}>()

const container = ref<HTMLDivElement | null>(null)
const editorView = shallowRef<import('@codemirror/view').EditorView | null>(null)
let loaded = false

async function initEditor() {
  if (!container.value || loaded) return
  loaded = true

  const [
    { EditorView, lineNumbers, keymap },
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
      backgroundColor: '#1d2021',
      color: '#ebdbb2',
      fontSize: '13px',
      fontFamily: 'var(--font-mono)',
    },
    '.cm-gutters': {
      backgroundColor: '#1d2021',
      color: '#665c54',
      border: 'none',
    },
    '.cm-activeLineGutter': {
      backgroundColor: '#282828',
    },
    '.cm-activeLine': {
      backgroundColor: '#28282860',
    },
    '&.cm-focused .cm-cursor': {
      borderLeftColor: '#83a598',
    },
    '&.cm-focused .cm-selectionBackground, .cm-selectionBackground': {
      backgroundColor: '#3c383660',
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
    class="overflow-hidden"
    style="min-height: 48px; background: var(--color-bg-hard); border-radius: 2px"
  />
</template>
