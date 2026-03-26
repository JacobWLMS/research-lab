import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'dashboard',
    component: () => import('./components/experiment/ExperimentDetail.vue'),
  },
  {
    path: '/experiment/:id',
    name: 'experiment',
    component: () => import('./components/experiment/ExperimentDetail.vue'),
    props: true,
  },
  {
    path: '/experiment/:experimentId/step/:stepName/canvas',
    name: 'canvas-report',
    component: () => import('./components/experiment/CanvasReport.vue'),
    meta: { fullscreen: true },
  },
  {
    path: '/experiment/:experimentId/assets',
    name: 'asset-library',
    component: () => import('./components/experiment/AssetLibrary.vue'),
    meta: { fullscreen: true },
  },
]

export const router = createRouter({
  history: createWebHistory(),
  routes,
})
