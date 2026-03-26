<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import ToastContainer from './components/shared/ToastContainer.vue'

const route = useRoute()
const isFullscreen = computed(() => (route.meta as Record<string, unknown>).fullscreen === true)
</script>

<template>
  <router-view />
  <ToastContainer />
</template>
