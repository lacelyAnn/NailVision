import { computed } from 'vue'
import { defineStore } from 'pinia'
import { useStorage } from '@vueuse/core'
import type { Design } from '@/lib/sd'

export interface SavedDesign {
  id: string
  at: number
  style: string
  kind: Design['kind']
  palette_hex: string[]
  zoom: string // base64 jpeg of the nails
  rating: number // 0 = not rated
}

const MAX = 30 // shortcut: localStorage holds ~5 MB, move to IndexedDB to keep more

export const useDesigns = defineStore('designs', () => {
  const items = useStorage<SavedDesign[]>('nailvision.designs', [])
  const get = (id: string) => items.value.find((x) => x.id === id)

  function add(jobId: string, d: Design) {
    const id = `${jobId}-${d.slot}`
    if (get(id)) return
    const { style, kind, palette_hex } = d
    items.value = [
      { id, at: Date.now(), style, kind, palette_hex, zoom: d.zoom_jpeg_b64, rating: 0 },
      ...items.value,
    ].slice(0, MAX)
  }
  const rate = (id: string, n: number) => {
    const x = get(id)
    if (x) x.rating = n
  }
  const remove = (id: string) => (items.value = items.value.filter((x) => x.id !== id))
  const clear = () => (items.value = [])

  const rated = computed(() => items.value.filter((x) => x.rating > 0))
  const average = computed(() =>
    rated.value.length ? rated.value.reduce((a, x) => a + x.rating, 0) / rated.value.length : 0,
  )
  // index 0 = 1 star ... index 4 = 5 stars
  const distribution = computed(() =>
    [1, 2, 3, 4, 5].map((n) => rated.value.filter((x) => x.rating === n).length),
  )

  return { items, get, add, rate, remove, clear, rated, average, distribution }
})
