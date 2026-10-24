import { ref, computed } from 'vue'
import { checkService, type Health } from '@/lib/sd'

export const service = ref<'checking' | 'online' | 'offline'>('checking')
export const health = ref<Health | null>(null)
export const fast = computed(() => ['cloudflare', 'cuda', 'mps'].includes(health.value?.mode ?? ''))
export const deviceLabel = computed(() => {
  const h = health.value
  if (!h) return ''
  return h.mode === 'cpu' ? 'CPU' : h.mode === 'mock' ? 'Test mode' : `GPU (${h.device ?? h.mode})`
})

export async function refreshService() {
  service.value = 'checking'
  health.value = await checkService()
  service.value = health.value ? 'online' : 'offline'
}
