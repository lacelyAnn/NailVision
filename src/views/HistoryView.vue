<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { RouterLink } from 'vue-router'
import { Trash2, ChevronLeft, ChevronRight } from 'lucide-vue-next'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import StarRating from '@/components/StarRating.vue'
import ImageViewer from '@/components/ImageViewer.vue'
import { useDesigns } from '@/stores/designs'

const store = useDesigns()
const filters = ['All', 'Rated', 'Unrated'] as const
const filter = ref<(typeof filters)[number]>('All')
const PAGE = 8
const page = ref(1)
const view = ref<string | null>(null)
const filtered = computed(() =>
  store.items.filter((x) => filter.value === 'All' || (filter.value === 'Rated') === x.rating > 0),
)
const pages = computed(() => Math.max(1, Math.ceil(filtered.value.length / PAGE)))
const shown = computed(() => {
  const p = Math.min(page.value, pages.value) // deleting the last item of a page falls back to the previous one
  return filtered.value.slice((p - 1) * PAGE, p * PAGE)
})
const current = computed(() => Math.min(page.value, pages.value))
watch(filter, () => (page.value = 1))
const when = (t: number) =>
  new Date(t).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })

const del = (id: string) =>
  confirm('Delete this design? This cannot be undone.') && store.remove(id)
const clearAll = () => confirm('Delete all saved designs? This cannot be undone.') && store.clear()
</script>

<template>
  <div>
    <div
      class="mb-6 flex flex-wrap items-end justify-between gap-4 bg-card/90 rounded-2xl p-4 backdrop-blur"
    >
      <div>
        <h1 class="font-display text-3xl font-extrabold tracking-tight">Previous designs</h1>
        <p class="text-muted-foreground mt-1.5 text-sm">
          Designs you generate are saved in this browser. Rate each one to remember your favourites.
        </p>
      </div>
      <div v-if="store.items.length" class="flex items-center gap-2">
        <div class="flex rounded-lg border p-0.5" role="group" aria-label="Filter designs">
          <button
            v-for="f in filters"
            :key="f"
            class="focus-visible:ring-ring/50 cursor-pointer rounded-md px-3 py-1 text-xs font-medium outline-none focus-visible:ring-[3px]"
            :class="filter === f ? 'bg-primary text-primary-foreground' : 'text-muted-foreground'"
            :aria-pressed="filter === f"
            @click="filter = f"
          >
            {{ f }}
          </button>
        </div>
        <Button variant="outline" size="sm" @click="clearAll"><Trash2 /> Clear all</Button>
      </div>
    </div>

    <div
      v-if="!store.items.length"
      class="text-muted-foreground bg-card/90 rounded-2xl border-2 border-dashed p-10 text-center text-sm"
    >
      <p>No saved designs yet.</p>
      <RouterLink to="/studio" class="text-primary mt-2 inline-block font-medium underline">
        Make your first design
      </RouterLink>
    </div>
    <p
      v-else-if="!shown.length"
      class="text-muted-foreground bg-card/90 w-fit rounded-lg p-3 text-sm"
    >
      No {{ filter.toLowerCase() }} designs.
    </p>

    <div class="grid grid-cols-[repeat(auto-fill,minmax(13rem,1fr))] gap-4">
      <Card
        v-for="d in shown"
        :key="d.id"
        class="hover:shadow-card overflow-hidden rounded-xl shadow-sm transition-shadow"
      >
        <button
          type="button"
          class="focus-visible:ring-ring/50 block w-full cursor-zoom-in outline-none focus-visible:ring-[3px]"
          :aria-label="`View ${d.style} design full screen`"
          @click="view = `data:image/jpeg;base64,${d.zoom}`"
        >
          <img
            :src="`data:image/jpeg;base64,${d.zoom}`"
            :alt="`${d.style} design`"
            class="bg-muted aspect-square w-full object-contain"
          />
        </button>
        <div class="flex flex-col gap-2 p-3">
          <div class="flex items-start justify-between gap-2">
            <div>
              <p class="font-display text-sm leading-tight font-bold capitalize">{{ d.style }}</p>
              <p class="text-muted-foreground text-xs">{{ when(d.at) }}</p>
            </div>
            <button
              class="text-muted-foreground hover:text-destructive focus-visible:ring-ring/50 cursor-pointer rounded p-1 outline-none focus-visible:ring-[3px]"
              :aria-label="`Delete ${d.style} design`"
              @click="del(d.id)"
            >
              <Trash2 class="size-4" />
            </button>
          </div>
          <div class="flex items-center gap-1">
            <i
              v-for="c in d.palette_hex"
              :key="c"
              class="size-4 rounded-full ring-1 ring-foreground/30"
              :style="{ background: c }"
            />
          </div>
          <StarRating
            :model-value="d.rating"
            :label="`Rate ${d.style} design`"
            @update:model-value="store.rate(d.id, $event)"
          />
        </div>
      </Card>
    </div>

    <nav
      v-if="pages > 1"
      class="mt-6 flex flex-wrap items-center justify-center gap-1"
      aria-label="Pagination"
    >
      <Button variant="outline" size="sm" :disabled="current === 1" @click="page = current - 1">
        <ChevronLeft /> Previous
      </Button>
      <button
        v-for="n in pages"
        :key="n"
        type="button"
        class="focus-visible:ring-ring/50 min-w-8 cursor-pointer rounded-md px-2 py-1 text-sm font-medium tabular-nums outline-none focus-visible:ring-[3px]"
        :class="
          n === current
            ? 'bg-primary text-primary-foreground'
            : 'text-muted-foreground hover:bg-accent'
        "
        :aria-current="n === current ? 'page' : undefined"
        :aria-label="`Page ${n}`"
        @click="page = n"
      >
        {{ n }}
      </button>
      <Button variant="outline" size="sm" :disabled="current === pages" @click="page = current + 1">
        Next <ChevronRight />
      </Button>
    </nav>
    <p v-if="filtered.length" class="text-muted-foreground mt-3 text-center text-xs">
      Showing {{ (current - 1) * PAGE + 1 }}–{{ (current - 1) * PAGE + shown.length }} of
      {{ filtered.length }}
    </p>

    <ImageViewer :src="view" alt="Design in full screen" @close="view = null" />
  </div>
</template>
