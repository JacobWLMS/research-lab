<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import AppShell from './components/layout/AppShell.vue'
import ToastContainer from './components/shared/ToastContainer.vue'

const route = useRoute()
const isFullscreen = computed(() => (route.meta as Record<string, unknown>).fullscreen === true)
</script>

<template>
  <!-- Fullscreen routes render without the shell -->
  <router-view v-if="isFullscreen" />
  <AppShell v-else>
    <router-view />
  </AppShell>
  <ToastContainer />
</template>
