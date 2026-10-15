<script setup lang="ts">
import { ref, computed, watch, nextTick, onMounted, onBeforeUnmount } from 'vue'
import { ImagePlus, Sparkles, Loader, Download, RefreshCw } from 'lucide-vue-next'
import { detectNails, drawDetections, nailMaskBlob, type Detection } from '@/lib/detector'
import { startJob, getJob, checkService, type Design } from '@/lib/sd'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card } from '@/components/ui/card'
import { Slider } from '@/components/ui/slider'

const canvas = ref<HTMLCanvasElement>()
const conf = ref([0.35])
const busy = ref(false)
const error = ref('')
const det = ref<Detection | null>(null)
const selected = computed(() => (det.value?.nails ?? []).slice(0, 5).map((n) => n.number)) // all nails, max 5
const hasPhoto = ref(false)
const photoName = ref('')
const photoUrl = ref('')
let img: HTMLImageElement | null = null
let file: File | null = null

const colors = ref(['#C8102E', '#F5F5F2', '#D4AF37'])
const steps = ref([30])
const genStatus = ref('')
const generating = ref(false)
const designs = ref<Design[]>([])
const service = ref<'checking' | 'online' | 'offline'>('checking')
let timer: number | undefined

const pending = computed(() => (generating.value ? Math.max(0, 5 - designs.value.length) : 0))

const redraw = () =>
  img && det.value && canvas.value && drawDetections(canvas.value, img, det.value, selected.value)

async function run() {
  if (!img) return
  busy.value = true
  error.value = ''
  try {
    det.value = await detectNails(img, conf.value[0] ?? 0.35)
    designs.value = []
    await nextTick()
    redraw()
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    busy.value = false
  }
}

function onFile(e: Event) {
  const input = e.target as HTMLInputElement
  const f = input.files?.[0]
  if (!f) return
  file = f
  photoName.value = f.name
  const i = new Image()
  i.onload = async () => {
    img = i
    hasPhoto.value = true
    await nextTick()
    run()
  }
  photoUrl.value = URL.createObjectURL(f)
  i.src = photoUrl.value
  input.value = ''
}

async function refreshService() {
  service.value = 'checking'
  service.value = (await checkService()) ? 'online' : 'offline'
}

async function generate() {
  const d = det.value
  const nails = d ? d.nails.filter((x) => selected.value.includes(x.number)) : []
  if (!nails.length || !img || !file || !d) return
  clearInterval(timer)
  error.value = ''
  designs.value = []
  generating.value = true
  genStatus.value = 'Sending the nails to the design service'
  try {
    const id = await startJob(
      file,
      await Promise.all(nails.map((n) => nailMaskBlob(img!, d, n))),
      colors.value,
      steps.value[0] ?? 30,
    )
    const poll = async () => {
      try {
        const j = await getJob(id)
        designs.value = j.designs
        genStatus.value =
          j.status === 'done' ? '' : `Painting design ${Math.min(5, j.designs.length + 1)} of 5`
        if (j.status === 'failed') error.value = j.error ?? 'Generation failed'
        if (j.status === 'done' || j.status === 'failed') {
          clearInterval(timer)
          generating.value = false
        }
      } catch (e) {
        error.value = e instanceof Error ? e.message : String(e)
        clearInterval(timer)
        generating.value = false
      }
    }
    timer = window.setInterval(poll, 3000)
  } catch (e) {
    genStatus.value = ''
    generating.value = false
    service.value = 'offline'
    error.value =
      (e instanceof Error ? e.message : String(e)) +
      '. Check that the design service is running on port 8000.'
  }
}

const match = (de: number) =>
  de < 10
    ? { text: 'Close match', cls: 'text-success' }
    : de < 20
      ? { text: 'Same colour family', cls: 'text-warning' }
      : { text: 'Loose match', cls: 'text-muted-foreground' }

watch(selected, redraw)
onMounted(refreshService)
onBeforeUnmount(() => clearInterval(timer))
</script>

<template>
  <div class="min-h-screen">
    <header class="bg-background/85 sticky top-0 z-10 border-b backdrop-blur">
      <div class="mx-auto flex h-16 max-w-6xl items-center gap-3 px-4 sm:px-6">
        <svg viewBox="0 0 40 48" class="h-8 w-7" aria-hidden="true">
          <path
            d="M6 44V18C6 8 12 3 20 3s14 5 14 15v26a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2Z"
            fill="var(--primary)"
          />
          <path
            d="M12 38V19c0-5 3-9 7-10"
            stroke="#fff"
            stroke-opacity=".75"
            stroke-width="3"
            stroke-linecap="round"
            fill="none"
          />
          <rect x="6" y="36" width="28" height="10" rx="2" fill="var(--foreground)" />
        </svg>
        <span class="font-display text-xl font-extrabold tracking-tight">NailVision</span>
        <span class="text-muted-foreground hidden text-sm sm:inline">Nail design studio</span>

        <button
          class="focus-visible:ring-ring/50 text-muted-foreground hover:text-foreground ml-auto flex cursor-pointer items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-medium outline-none focus-visible:ring-[3px]"
          :title="'Recheck the design service'"
          @click="refreshService"
        >
          <span
            class="size-2 rounded-full"
            :class="{
              'bg-success': service === 'online',
              'bg-destructive': service === 'offline',
              'bg-muted-foreground animate-pulse': service === 'checking',
            }"
          />
          Design service
          {{ service === 'online' ? 'ready' : service === 'offline' ? 'offline' : 'checking' }}
          <RefreshCw class="size-3" />
        </button>
      </div>
    </header>

    <main class="mx-auto max-w-6xl px-4 py-8 pb-20 sm:px-6">
      <div class="grid gap-8 lg:grid-cols-[minmax(0,1fr)_360px]">
        <!-- stage -->
        <section aria-label="Hand photo">
          <label
            v-if="!hasPhoto"
            class="bg-card hover:border-primary focus-within:ring-ring/50 flex min-h-[460px] cursor-pointer flex-col items-center justify-center gap-4 rounded-2xl border-2 border-dashed p-8 text-center transition-colors focus-within:ring-[3px]"
          >
            <span
              class="bg-accent text-primary flex size-14 items-center justify-center rounded-full"
            >
              <ImagePlus class="size-6" />
            </span>
            <span class="font-display text-2xl font-bold tracking-tight"
              >Start with a hand photo</span
            >
            <span class="text-muted-foreground max-w-sm text-sm leading-relaxed">
              Nails facing the camera in even light works best. NailVision finds each nail and
              numbers it from left to right.
            </span>
            <Button as="span" size="lg">Choose a photo</Button>
            <input type="file" accept="image/*" class="sr-only" @change="onFile" />
          </label>

          <Card v-else class="overflow-hidden rounded-2xl shadow-sm">
            <div class="flex items-center gap-3 border-b px-4 py-3">
              <div class="min-w-0">
                <p class="truncate text-sm font-semibold">{{ photoName }}</p>
                <p class="text-muted-foreground text-xs">
                  <template v-if="busy">Detecting nails</template>
                  <template v-else-if="det">
                    {{ det.nails.length }} {{ det.nails.length === 1 ? 'nail' : 'nails' }} found in
                    {{ det.ms.toFixed(0) }} ms
                  </template>
                </p>
              </div>
              <label class="ml-auto">
                <Button as="span" variant="outline" size="sm">Change photo</Button>
                <input type="file" accept="image/*" class="sr-only" @change="onFile" />
              </label>
            </div>
            <div class="bg-muted/50 relative p-3">
              <canvas
                ref="canvas"
                class="mx-auto aspect-square w-full max-w-[640px] rounded-lg object-contain"
              />
              <div
                v-if="busy"
                class="bg-background/60 absolute inset-0 flex items-center justify-center backdrop-blur-[2px]"
              >
                <span
                  class="bg-card flex items-center gap-2 rounded-full border px-4 py-2 text-sm shadow"
                >
                  <Loader class="size-4 animate-spin" /> Finding nails
                </span>
              </div>
            </div>
          </Card>

          <p
            v-if="error"
            role="alert"
            class="border-destructive/30 bg-destructive/5 text-destructive mt-4 rounded-lg border p-3 text-sm"
          >
            {{ error }}
          </p>
        </section>

        <!-- controls -->
        <aside class="flex flex-col gap-4" aria-label="Design controls">
          <Card class="p-5">
            <div class="flex items-baseline justify-between">
              <h2 class="font-display text-base font-bold">Detection</h2>
              <span class="text-muted-foreground text-xs tabular-nums"
                >Confidence {{ conf[0]?.toFixed(2) }}</span
              >
            </div>
            <Slider
              v-model="conf"
              :min="0.1"
              :max="0.9"
              :step="0.05"
              class="mt-3"
              aria-label="Detection confidence"
              :disabled="!hasPhoto"
              @value-commit="run"
            />
            <p class="text-muted-foreground mt-2 text-xs leading-relaxed">
              Raise it if non-nails are picked up. Lower it if a nail is missed.
            </p>
          </Card>

          <Card class="p-5" :class="{ 'opacity-60': !selected.length }">
            <h2 class="font-display text-base font-bold">Polishes</h2>
            <p class="text-muted-foreground mt-1 text-xs leading-relaxed">
              Each of the first three designs uses one of these as its base. Every design is applied to all detected nails (up to 5).
            </p>
            <div class="mt-3 flex gap-3">
              <label v-for="(_, i) in colors" :key="i" class="flex flex-1 flex-col gap-1.5 text-xs">
                <span
                  class="focus-within:ring-ring/50 relative block h-12 overflow-hidden rounded-lg border shadow-sm focus-within:ring-[3px]"
                  :style="{ background: colors[i] }"
                >
                  <input
                    v-model="colors[i]"
                    type="color"
                    class="absolute inset-0 size-full cursor-pointer opacity-0"
                    :aria-label="`Polish ${i + 1}`"
                  />
                </span>
                <span class="text-muted-foreground text-center tabular-nums">{{ colors[i] }}</span>
              </label>
            </div>

            <div class="mt-5 border-t pt-4">
              <div class="flex justify-between text-sm">
                <span class="font-medium">Quality steps</span>
                <span class="text-muted-foreground tabular-nums">{{ steps[0] }}</span>
              </div>
              <Slider
                v-model="steps"
                :min="5"
                :max="50"
                :step="1"
                class="mt-3"
                aria-label="Quality steps"
              />
              <p class="text-muted-foreground mt-2 text-xs leading-relaxed">
                30 is the tuned setting. Fewer steps run faster but look rougher.
              </p>
            </div>

            <Button
              size="lg"
              class="mt-5 w-full"
              :disabled="!selected.length || generating"
              @click="generate"
            >
              <Loader v-if="generating" class="animate-spin" /><Sparkles v-else />
              {{ generating ? 'Generating' : 'Generate 5 designs' }}
            </Button>
            <p v-if="!selected.length" class="text-muted-foreground mt-2 text-center text-xs">
              Upload a photo with visible nails first.
            </p>
            <p
              v-if="genStatus"
              role="status"
              class="text-muted-foreground mt-3 text-center text-xs"
            >
              {{ genStatus }}. On a CPU each design takes a few minutes.
            </p>
          </Card>
        </aside>
      </div>

      <!-- results -->
      <section v-if="designs.length || pending" class="mt-12" aria-label="Designs">
        <div class="flex items-end justify-between">
          <div>
            <h2 class="font-display text-2xl font-bold tracking-tight">
              Designs
            </h2>
            <p class="text-muted-foreground text-sm">
              Three use your polishes. Two are suggestions we picked. Each appears as soon as it is finished.
            </p>
          </div>
        </div>
        <div
          class="mt-5 grid grid-cols-[repeat(auto-fill,14rem)] justify-center gap-4 sm:justify-start"
        >
          <Card v-for="d in designs" :key="d.slot" class="overflow-hidden rounded-xl shadow-sm">
            <img
              :src="`data:image/jpeg;base64,${d.zoom_jpeg_b64}`"
              :alt="`${d.style} design on nails ${selected.join(', ')}`"
              class="bg-muted size-56 object-contain"
            />
            <div class="flex flex-col gap-2 p-3">
              <div>
                <p class="font-display text-sm leading-tight font-bold capitalize">{{ d.style }}</p>
                <p class="text-muted-foreground text-xs">
                  {{ d.kind === 'palette' ? 'Your polishes' : 'Suggested' }}
                </p>
              </div>
              <div class="flex items-center gap-1">
                <i
                  v-for="c in d.palette_hex"
                  :key="c"
                  class="size-4 rounded-full ring-1 ring-black/10"
                  :style="{ background: c }"
                />
                <a
                  :href="`data:image/jpeg;base64,${d.full_jpeg_b64}`"
                  :download="`nailvision-design${d.slot}.jpg`"
                  class="text-muted-foreground hover:text-foreground focus-visible:ring-ring/50 ml-auto rounded p-1 outline-none focus-visible:ring-[3px]"
                  title="Save full photo"
                  aria-label="Save full photo"
                >
                  <Download class="size-4" />
                </a>
              </div>
              <p class="text-xs font-medium" :class="match(d.delta_e).cls">
                {{ d.kind === 'palette' ? match(d.delta_e).text : 'Random palette' }}
              </p>
            </div>
          </Card>

          <Card
            v-for="k in pending"
            :key="`s${k}`"
            class="overflow-hidden rounded-xl"
            aria-hidden="true"
          >
            <div class="bg-muted size-56 animate-pulse" />
            <div class="flex flex-col gap-2 p-3">
              <div class="bg-muted h-3.5 w-2/3 animate-pulse rounded" />
              <div class="bg-muted h-3 w-1/2 animate-pulse rounded" />
            </div>
          </Card>
        </div>
      </section>
    </main>

    <footer class="text-muted-foreground border-t py-6 text-center text-xs">
      <Badge variant="outline">Runs on this computer</Badge>
      <span class="ml-2">Photos stay on your device. Nothing is uploaded.</span>
    </footer>
  </div>
</template>
