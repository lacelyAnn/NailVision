import { createRouter, createWebHashHistory } from 'vue-router'
import { useAuth } from '@/stores/auth'

const home = { client: '/client', technician: '/tech' } as const

// hash history: deep links work on static hosting without a rewrite rule
const router = createRouter({
  history: createWebHashHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/', name: 'landing', component: () => import('@/views/LandingView.vue') },
    { path: '/login', name: 'login', component: () => import('@/views/LoginView.vue') },
    {
      path: '/client',
      meta: { role: 'client' },
      children: [
        { path: '', name: 'dashboard', component: () => import('@/views/DashboardView.vue') },
        { path: 'studio', name: 'studio', component: () => import('@/views/StudioView.vue') },
        { path: 'history', name: 'history', component: () => import('@/views/HistoryView.vue') },
        { path: 'bookings', name: 'bookings', component: () => import('@/views/BookingsView.vue') },
      ],
    },
    {
      path: '/tech',
      meta: { role: 'technician' },
      children: [{ path: '', name: 'tech', component: () => import('@/views/BookingsView.vue') }],
    },
  ],
})

router.beforeEach(async (to) => {
  const auth = useAuth()
  await auth.ready()
  const role = auth.profile?.role
  // public pages; signed-in users skip straight to their own area
  if (to.name === 'login' || to.name === 'landing') return role ? home[role] : true
  if (!role) return { name: 'login' }
  if (to.meta.role && to.meta.role !== role) return home[role] // each role stays in its own area
})

export default router
