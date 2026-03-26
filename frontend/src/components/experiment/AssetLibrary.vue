<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { AssetImage, AssetArtifact, AssetsResponse } from '../../types'

const route = useRoute()
const router = useRouter()

const experimentId = computed(() => route.params.experimentId as string)

const images = ref<AssetImage[]>([])
const artifacts = ref<AssetArtifact[]>([])
const loading = ref(true)
const error = ref<string | null>(null)
const ready = ref(false)
const filterStep = ref<string>('')
const lightboxIndex = ref<number | null>(null)

// Unique step names for the filter dropdown
const stepNames = computed(() => {
  const names = new Set<string>()
  for (const img of images.value) names.add(img.step_name)
  for (const art of artifacts.value) if (art.step_name) names.add(art.step_name)
  return Array.from(names).sort()
})

const filteredImages = computed(() => {
  if (!filterStep.value) return images.value
  return images.value.filter((img) => img.step_name === filterStep.value)
})

const filteredArtifacts = computed(() => {
  if (!filterStep.value) return artifacts.value
  return artifacts.value.filter((art) => !art.step_name || art.step_name === filterStep.value)
})

const lightboxImage = computed<AssetImage | null>(() => {
  if (lightboxIndex.value === null) return null
  return images.value.find((img) => img.index === lightboxIndex.value) ?? null
})

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`
}

function imgSrc(img: AssetImage): string {
  return `data:${img.mime};base64,${img.data}`
}

function openLightbox(index: number) {
  lightboxIndex.value = index
}

function closeLightbox() {
  lightboxIndex.value = null
}

function onLightboxKeydown(e: KeyboardEvent) {
  if (lightboxIndex.value === null) return
  if (e.key === 'Escape') {
    closeLightbox()
    e.stopPropagation()
    return
  }
  const currentList = filteredImages.value
  const curIdx = currentList.findIndex((img) => img.index === lightboxIndex.value)
  if (e.key === 'ArrowRight' && curIdx < currentList.length - 1) {
    lightboxIndex.value = currentList[curIdx + 1].index
  } else if (e.key === 'ArrowLeft' && curIdx > 0) {
    lightboxIndex.value = currentList[curIdx - 1].index
  }
}

async function fetchAssets() {
  loading.value = true
  error.value = null
  try {
    const res = await fetch(`/api/experiments/${experimentId.value}/assets`)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data: AssetsResponse = await res.json()
    images.value = data.images
    artifacts.value = data.artifacts
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    loading.value = false
    requestAnimationFrame(() => { ready.value = true })
  }
}

function downloadAll() {
  const url = `/api/experiments/${experimentId.value}/assets/download`
  const a = document.createElement('a')
  a.href = url
  a.download = ''
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
}

function downloadArtifact(art: AssetArtifact) {
  // Use the single-asset endpoint if it's an image, otherwise direct path is backend-internal
  // For artifacts, we trigger a download via the zip with just that file
  // Best approach: create a simple one-file download link
  const url = `/api/experiments/${experimentId.value}/assets/download`
  const a = document.createElement('a')
  a.href = url
  a.download = ''
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
}

function goBack() {
  router.push({ name: 'experiment', params: { id: experimentId.value } })
}

function onKeydown(e: KeyboardEvent) {
  if (lightboxIndex.value !== null) {
    onLightboxKeydown(e)
    return
  }
  if (e.key === 'Escape') {
    goBack()
  }
}

onMounted(() => {
  fetchAssets()
  document.addEventListener('keydown', onKeydown)
})

onUnmounted(() => {
  document.removeEventListener('keydown', onKeydown)
})

watch(experimentId, () => {
  fetchAssets()
})
</script>

<template>
  <div class="asset-library" :class="{ 'asset-library--ready': ready }">
    <!-- Header -->
    <header class="asset-library__header">
      <div class="asset-library__header-left">
        <button class="asset-library__back" @click="goBack" title="Back to experiment (Esc)">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M19 12H5m0 0l7 7m-7-7l7-7" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          <span>Back</span>
        </button>

        <div class="asset-library__divider" />

        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="color: var(--c-fg-muted)">
          <rect x="3" y="3" width="7" height="7" rx="1"/>
          <rect x="14" y="3" width="7" height="7" rx="1"/>
          <rect x="3" y="14" width="7" height="7" rx="1"/>
          <rect x="14" y="14" width="7" height="7" rx="1"/>
        </svg>
        <span class="asset-library__title">Assets</span>
        <span v-if="!loading" class="asset-library__count">
          ({{ filteredImages.length }} image{{ filteredImages.length !== 1 ? 's' : '' }}<template v-if="filteredArtifacts.length">, {{ filteredArtifacts.length }} artifact{{ filteredArtifacts.length !== 1 ? 's' : '' }}</template>)
        </span>
      </div>

      <div class="asset-library__header-right">
        <!-- Step filter -->
        <select
          v-if="stepNames.length > 1"
          v-model="filterStep"
          class="asset-library__filter"
        >
          <option value="">All steps</option>
          <option v-for="name in stepNames" :key="name" :value="name">{{ name }}</option>
        </select>

        <!-- Download All -->
        <button
          v-if="images.length > 0 || artifacts.length > 0"
          class="asset-library__download-all"
          @click="downloadAll"
          title="Download all assets as a zip"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" stroke-linecap="round" stroke-linejoin="round"/>
            <polyline points="7 10 12 15 17 10" stroke-linecap="round" stroke-linejoin="round"/>
            <line x1="12" y1="15" x2="12" y2="3" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          Download All
        </button>

        <span class="asset-library__hint">Esc to close</span>
      </div>
    </header>

    <!-- Loading -->
    <div v-if="loading" class="asset-library__state">
      <svg class="animate-spin" width="20" height="20" viewBox="0 0 24 24" fill="none" style="color: var(--c-fg-dim)">
        <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="2" opacity="0.25"/>
        <path d="M4 12a8 8 0 018-8" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
      </svg>
      <span>Loading assets...</span>
    </div>

    <!-- Error -->
    <div v-else-if="error" class="asset-library__state asset-library__state--error">
      <span>Failed to load: {{ error }}</span>
      <button class="asset-library__retry" @click="fetchAssets">Retry</button>
    </div>

    <!-- Empty -->
    <div v-else-if="images.length === 0 && artifacts.length === 0" class="asset-library__state">
      <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="color: var(--c-fg-dim)">
        <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
        <circle cx="8.5" cy="8.5" r="1.5"/>
        <polyline points="21 15 16 10 5 21" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
      <span>No assets yet</span>
      <p style="color: var(--c-fg-dim); font-size: 0.75rem; margin: 0">
        Run experiment steps to generate images and artifacts
      </p>
      <button class="asset-library__back-link" @click="goBack">Go back</button>
    </div>

    <!-- Content -->
    <div v-else class="asset-library__body">
      <!-- Image grid -->
      <div v-if="filteredImages.length > 0" class="asset-library__section">
        <div class="asset-library__grid">
          <div
            v-for="img in filteredImages"
            :key="img.index"
            class="asset-library__card"
            @click="openLightbox(img.index)"
          >
            <div class="asset-library__card-thumb">
              <img :src="imgSrc(img)" :alt="img.title" loading="lazy" />
            </div>
            <div class="asset-library__card-info">
              <span class="asset-library__card-step">{{ img.step_name }}</span>
              <span class="asset-library__card-title">{{ img.title }}</span>
              <span v-if="img.canvas_name" class="asset-library__card-source">{{ img.canvas_name }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Artifacts table -->
      <div v-if="filteredArtifacts.length > 0" class="asset-library__section">
        <h3 class="asset-library__section-title">Artifacts</h3>
        <table class="asset-library__table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Format</th>
              <th>Size</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="art in filteredArtifacts" :key="art.name">
              <td class="asset-library__table-name">{{ art.name }}</td>
              <td class="asset-library__table-format">{{ art.format }}</td>
              <td class="asset-library__table-size">{{ formatSize(art.size_bytes) }}</td>
              <td>
                <button class="asset-library__table-dl" @click="downloadArtifact(art)" title="Download">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" stroke-linecap="round" stroke-linejoin="round"/>
                    <polyline points="7 10 12 15 17 10" stroke-linecap="round" stroke-linejoin="round"/>
                    <line x1="12" y1="15" x2="12" y2="3" stroke-linecap="round" stroke-linejoin="round"/>
                  </svg>
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Lightbox overlay -->
    <Teleport to="body">
      <div
        v-if="lightboxImage"
        class="asset-library__lightbox"
        @click.self="closeLightbox"
      >
        <div class="asset-library__lightbox-content">
          <img :src="imgSrc(lightboxImage)" :alt="lightboxImage.title" />
          <div class="asset-library__lightbox-caption">
            <span class="asset-library__lightbox-title">{{ lightboxImage.title }}</span>
            <span class="asset-library__lightbox-meta">
              {{ lightboxImage.step_name }}
              <template v-if="lightboxImage.canvas_name"> / {{ lightboxImage.canvas_name }}</template>
            </span>
          </div>
        </div>
        <button class="asset-library__lightbox-close" @click="closeLightbox" title="Close (Esc)">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M18 6L6 18M6 6l12 12" stroke-linecap="round"/>
          </svg>
        </button>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.asset-library {
  position: fixed;
  inset: 0;
  z-index: 100;
  display: flex;
  flex-direction: column;
  background: var(--c-bg-hard);
  color: var(--c-fg);
  opacity: 0;
  transition: opacity 0.2s cubic-bezier(0.15, 0.9, 0.25, 1);
}

.asset-library--ready {
  opacity: 1;
}

/* ---- Header ---- */
.asset-library__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 2.75rem;
  padding: 0 1rem;
  background: var(--c-surface);
  border-bottom: 1px solid var(--c-border);
  flex-shrink: 0;
}

.asset-library__header-left {
  display: flex;
  align-items: center;
  gap: 0.625rem;
}

.asset-library__header-right {
  display: flex;
  align-items: center;
  gap: 0.625rem;
}

.asset-library__back {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.25rem 0.625rem;
  font-size: 0.75rem;
  font-weight: 500;
  color: var(--c-fg-muted);
  background: var(--c-bg1);
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: background 0.12s, color 0.12s;
}

.asset-library__back:hover {
  background: var(--c-surface-active);
  color: var(--c-fg);
}

.asset-library__divider {
  width: 1px;
  height: 1rem;
  background: var(--c-bg3);
}

.asset-library__title {
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--c-fg);
}

.asset-library__count {
  font-size: 0.75rem;
  color: var(--c-fg-muted);
}

.asset-library__filter {
  font-size: 0.75rem;
  padding: 0.2rem 0.5rem;
  background: var(--c-bg1);
  color: var(--c-fg);
  border: 1px solid var(--c-border);
  border-radius: var(--radius-sm);
  cursor: pointer;
  outline: none;
}

.asset-library__filter:focus {
  border-color: var(--c-aqua);
}

.asset-library__download-all {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  padding: 0.25rem 0.75rem;
  font-size: 0.75rem;
  font-weight: 500;
  color: var(--c-bg-hard);
  background: var(--c-aqua);
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: opacity 0.12s;
}

.asset-library__download-all:hover {
  opacity: 0.85;
}

.asset-library__hint {
  font-size: 0.6875rem;
  color: var(--c-fg-dim);
  padding: 0.125rem 0.5rem;
  background: var(--c-bg1);
  border-radius: var(--radius-sm);
}

/* ---- States ---- */
.asset-library__state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.75rem;
  font-size: 0.875rem;
  color: var(--c-fg-dim);
}

.asset-library__state--error {
  color: var(--c-red);
}

.asset-library__retry {
  padding: 0.375rem 1rem;
  font-size: 0.75rem;
  font-weight: 500;
  color: var(--c-fg);
  background: var(--c-bg2);
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: background 0.12s;
}

.asset-library__retry:hover {
  background: var(--c-bg3);
}

.asset-library__back-link {
  padding: 0.25rem 0.75rem;
  font-size: 0.75rem;
  color: var(--c-aqua);
  background: var(--c-bg1);
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: background 0.12s;
}

.asset-library__back-link:hover {
  background: var(--c-surface-hover);
}

/* ---- Body ---- */
.asset-library__body {
  flex: 1;
  overflow-y: auto;
  padding: 1.25rem;
}

.asset-library__section {
  max-width: 75rem;
  margin: 0 auto 1.5rem;
}

.asset-library__section-title {
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--c-fg-muted);
  margin: 0 0 0.625rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

/* ---- Image grid ---- */
.asset-library__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(10rem, 1fr));
  gap: 0.75rem;
}

.asset-library__card {
  border: 1px solid var(--c-border);
  border-radius: 2px;
  background: var(--c-surface);
  cursor: pointer;
  transition: border-color 0.12s, box-shadow 0.12s;
  overflow: hidden;
}

.asset-library__card:hover {
  border-color: var(--c-fg-dim);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
}

.asset-library__card-thumb {
  width: 100%;
  aspect-ratio: 1;
  overflow: hidden;
  background: var(--c-bg);
  display: flex;
  align-items: center;
  justify-content: center;
}

.asset-library__card-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform 0.15s;
}

.asset-library__card:hover .asset-library__card-thumb img {
  transform: scale(1.03);
}

.asset-library__card-info {
  padding: 0.375rem 0.5rem;
  display: flex;
  flex-direction: column;
  gap: 0.125rem;
  border-top: 1px solid var(--c-border-subtle);
}

.asset-library__card-step {
  font-size: 0.625rem;
  font-family: var(--font-mono);
  color: var(--c-aqua);
  text-transform: uppercase;
  letter-spacing: 0.02em;
}

.asset-library__card-title {
  font-size: 0.75rem;
  color: var(--c-fg);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.asset-library__card-source {
  font-size: 0.625rem;
  color: var(--c-fg-dim);
}

/* ---- Artifacts table ---- */
.asset-library__table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.8125rem;
}

.asset-library__table th {
  text-align: left;
  font-size: 0.6875rem;
  font-weight: 500;
  color: var(--c-fg-dim);
  text-transform: uppercase;
  letter-spacing: 0.04em;
  padding: 0.375rem 0.625rem;
  border-bottom: 1px solid var(--c-border);
}

.asset-library__table td {
  padding: 0.5rem 0.625rem;
  border-bottom: 1px solid var(--c-border-subtle);
}

.asset-library__table tr:hover td {
  background: var(--c-surface-hover);
}

.asset-library__table-name {
  font-family: var(--font-mono);
  color: var(--c-fg);
}

.asset-library__table-format {
  font-family: var(--font-mono);
  color: var(--c-fg-muted);
}

.asset-library__table-size {
  font-family: var(--font-mono);
  color: var(--c-fg-muted);
  white-space: nowrap;
}

.asset-library__table-dl {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0.25rem;
  background: transparent;
  border: 1px solid var(--c-border);
  border-radius: var(--radius-sm);
  color: var(--c-fg-muted);
  cursor: pointer;
  transition: background 0.12s, color 0.12s;
}

.asset-library__table-dl:hover {
  background: var(--c-surface-active);
  color: var(--c-fg);
}

/* ---- Lightbox ---- */
.asset-library__lightbox {
  position: fixed;
  inset: 0;
  z-index: 200;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--c-overlay);
  animation: fade-in 0.15s ease;
}

.asset-library__lightbox-content {
  max-width: 90vw;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.asset-library__lightbox-content img {
  max-width: 90vw;
  max-height: 80vh;
  object-fit: contain;
  border-radius: 2px;
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.4);
}

.asset-library__lightbox-caption {
  margin-top: 0.75rem;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.25rem;
}

.asset-library__lightbox-title {
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--c-fg);
}

.asset-library__lightbox-meta {
  font-size: 0.75rem;
  font-family: var(--font-mono);
  color: var(--c-fg-muted);
}

.asset-library__lightbox-close {
  position: absolute;
  top: 1rem;
  right: 1rem;
  padding: 0.375rem;
  background: var(--c-bg2);
  border: none;
  border-radius: var(--radius-sm);
  color: var(--c-fg-muted);
  cursor: pointer;
  transition: background 0.12s, color 0.12s;
}

.asset-library__lightbox-close:hover {
  background: var(--c-bg3);
  color: var(--c-fg);
}
</style>
