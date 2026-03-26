import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

const AppShell = () => import('./components/layout/AppShell.vue')

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'home',
    component: AppShell,
  },
  {
    path: '/experiment/:id',
    name: 'experiment',
    component: AppShell,
    props: true,
  },
  {
    path: '/experiment/:id/step/:stepName',
    name: 'step',
    component: AppShell,
    props: true,
  },
  {
    path: '/experiment/:id/assets',
    name: 'assets',
    component: () => import('./components/experiment/AssetLibrary.vue'),
    meta: { fullscreen: true },
  },
]

export const router = createRouter({
  history: createWebHistory(),
  routes,
})
