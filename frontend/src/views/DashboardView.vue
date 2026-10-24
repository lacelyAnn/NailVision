<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink } from 'vue-router'
import { Sparkles, Images, Star, Palette, Cpu } from 'lucide-vue-next'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import StarRating from '@/components/StarRating.vue'
import { useDesigns } from '@/stores/designs'
import { service, deviceLabel } from '@/lib/service'

const store = useDesigns()
const recent = computed(() => store.items.slice(0, 4))
const topCount = computed(() => Math.max(1, ...store.distribution))
const stats = computed(() => [
  { label: 'Designs made', value: String(store.items.length), icon: Palette },
  {
    label: 'Average rating',
    value: store.rated.length ? store.average.toFixed(1) : '–',
    icon: Star,
  },
  { label: 'Rated designs', value: `${store.rated.length} of ${store.items.length}`, icon: Images },
  {
    label: 'Design service',
    value:
      service.value === 'online' ? 'Ready' : service.value === 'offline' ? 'Offline' : 'Checking',
    sub: deviceLabel.value,
    icon: Cpu,
  },
])
</script>

<template>
  <div class="flex flex-col gap-6">
    <section
      class="from-accent to-card relative overflow-hidden rounded-2xl border bg-gradient-to-br shadow-sm"
    >
      <div class="relative flex flex-col items-start gap-6 p-6 sm:flex-row sm:items-center sm:p-8">
        <div>
          <h1 class="font-display text-3xl font-extrabold tracking-tight sm:text-4xl">
            Welcome to <span>Nail</span><span class="text-primary">Vision</span>
          </h1>
          <p class="text-muted-foreground mt-2 max-w-md text-sm leading-relaxed">
            Capture your hand, choose your polishes, and get five designs painted on your nails.
          </p>
          <div class="mt-4 flex flex-wrap gap-2">
            <Button as-child size="lg">
              <RouterLink to="/client/studio"><Sparkles /> New design</RouterLink>
            </Button>
            <Button as-child size="lg" variant="outline">
              <RouterLink to="/client/history"><Images /> Previous designs</RouterLink>
            </Button>
          </div>
        </div>
      </div>
    </section>

    <section class="grid grid-cols-2 gap-4 lg:grid-cols-4" aria-label="Summary">
      <Card v-for="s in stats" :key="s.label" class="p-4">
        <div class="text-muted-foreground flex items-center gap-2 text-xs font-medium">
          <span class="bg-accent text-primary grid size-7 place-items-center rounded-lg"
            ><component :is="s.icon" class="size-4"
          /></span>
          {{ s.label }}
        </div>
        <p class="font-display mt-2 text-2xl font-extrabold tabular-nums">{{ s.value }}</p>
        <p v-if="s.sub" class="text-muted-foreground truncate text-xs">{{ s.sub }}</p>
      </Card>
    </section>

    <div class="grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
      <Card class="p-5">
        <div class="flex items-baseline justify-between">
          <h2 class="font-display text-base font-bold">Recent designs</h2>
          <RouterLink to="/client/history" class="text-primary text-xs font-medium underline">
            View all
          </RouterLink>
        </div>
        <p
          v-if="!recent.length"
          class="text-muted-foreground mt-4 rounded-xl border-2 border-dashed p-6 text-center text-sm"
        >
          Nothing here yet. Make a design to see it here.
        </p>
        <div v-else class="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <div v-for="d in recent" :key="d.id" class="flex flex-col gap-1.5">
            <img
              :src="`data:image/jpeg;base64,${d.zoom}`"
              :alt="`${d.style} design`"
              class="bg-muted aspect-square w-full rounded-lg object-contain"
            />
            <p class="truncate text-xs font-semibold capitalize">{{ d.style }}</p>
            <StarRating :model-value="d.rating" readonly :label="`${d.style} rating`" />
          </div>
        </div>
      </Card>

      <Card class="p-5">
        <h2 class="font-display text-base font-bold">How you rate designs</h2>
        <p v-if="!store.rated.length" class="text-muted-foreground mt-4 text-sm">
          Rate a design with the stars and your ratings show up here.
        </p>
        <ul v-else class="mt-4 flex flex-col gap-2">
          <li v-for="n in [5, 4, 3, 2, 1]" :key="n" class="flex items-center gap-2 text-xs">
            <span class="w-12 tabular-nums">{{ n }} star{{ n > 1 ? 's' : '' }}</span>
            <span class="bg-muted h-2 flex-1 overflow-hidden rounded-full">
              <span
                class="bg-primary block h-full rounded-full transition-all"
                :style="{ width: `${((store.distribution[n - 1] ?? 0) / topCount) * 100}%` }"
              />
            </span>
            <span class="text-muted-foreground w-5 text-right tabular-nums">
              {{ store.distribution[n - 1] }}
            </span>
          </li>
        </ul>
      </Card>
    </div>
  </div>
</template>
