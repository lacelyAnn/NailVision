import { createRouter, createWebHashHistory } from 'vue-router'

// hash history: deep links work on static hosting without a rewrite rule
const router = createRouter({
  history: createWebHashHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/', name: 'dashboard', component: () => import('@/views/DashboardView.vue') },
    { path: '/studio', name: 'studio', component: () => import('@/views/StudioView.vue') },
    { path: '/history', name: 'history', component: () => import('@/views/HistoryView.vue') },
  ],
})

export default router
