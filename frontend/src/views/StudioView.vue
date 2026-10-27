<script setup lang="ts">
import { ref, computed, watch, nextTick, onBeforeUnmount, onDeactivated } from 'vue'
import {
  ScanLine,
  X,
  Sparkles,
  Loader,
  Download,
  Check,
  Pipette,
  CalendarCheck,
} from 'lucide-vue-next'
import { detectNails, drawDetections, nailMaskBlob, photoBlob, type Detection } from '@/lib/detector'
import { startJob, getJob, type Design } from '@/lib/sd'
import { service, fast } from '@/lib/service'
import { useDesigns, type SavedDesign } from '@/stores/designs'
import StarRating from '@/components/StarRating.vue'
import ImageViewer from '@/components/ImageViewer.vue'
import BookDialog from '@/components/BookDialog.vue'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card } from '@/components/ui/card'
import { Slider } from '@/components/ui/slider'

const store = useDesigns()
const view = ref<string | null>(null)
const booking = ref<SavedDesign | null>(null)
const jobId = ref('')
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

const colors = ref(['#C37F92', '#4D4E6E', '#F2B5B0']) // mauve, slate, blush from the logo swatches
const steps = ref([30]) // diffusion steps, picked through the friendly presets below
const qualities = [
  { name: 'Quick', hint: 'Fastest, rougher', steps: 15 },
  { name: 'Balanced', hint: 'Recommended', steps: 30 },
  { name: 'Best', hint: 'Slowest, finest', steps: 45 },
]
const genStatus = ref('')
const generating = ref(false)
const progress = ref(0)
const now = ref(Date.now())
let designStart = Date.now()

// Seconds one design takes: the average of finished ones, else extrapolated from the current one.
const perDesign = computed(() => {
  const d = designs.value
  if (d.length) return d.reduce((a, x) => a + x.seconds, 0) / d.length
  return progress.value >= 3 ? ((now.value - designStart) / 1000 / progress.value) * 100 : 0
})
const left = computed(() => perDesign.value * (5 - designs.value.length - progress.value / 100))
const overall = computed(() =>
  Math.min(100, Math.round(((designs.value.length + progress.value / 100) / 5) * 100)),
)
const fmt = (s: number) => (s < 60 ? 'under a minute' : `about ${Math.ceil(s / 60)} min`)
const designs = ref<Design[]>([])
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

function load(f: Blob, name: string) {
  photoName.value = name
  const i = new Image()
  i.onload = async () => {
    img = i
    hasPhoto.value = true
    await nextTick()
    run()
  }
  photoUrl.value = URL.createObjectURL(f)
  i.src = photoUrl.value
}

// live camera scan: rear camera on phones, webcam on computers.
// Nails are detected on every frame; once the same count holds for STEADY frames, that frame becomes the photo.
const STEADY = 3
const scanning = ref(false)
const video = ref<HTMLVideoElement>()
const overlay = ref<HTMLCanvasElement>()
const liveCount = ref(0)
const steady = ref(0)
const countdown = ref(0) // seconds left before detection starts, time to place the hand
let stream: MediaStream | null = null
let scanId = 0

async function startScan() {
  error.value = ''
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: 'environment', width: { ideal: 1920 }, height: { ideal: 1920 } },
      audio: false,
    })
    scanning.value = true
    liveCount.value = steady.value = 0
    await nextTick()
    video.value!.srcObject = stream
    scanLoop(++scanId)
  } catch (e) {
    stopScan()
    error.value =
      e instanceof DOMException && e.name === 'NotAllowedError'
        ? 'Camera access was blocked. Allow the camera in your browser or app settings, then try again.'
        : 'No camera could be opened on this device.'
  }
}

function stopScan() {
  scanId++ // ends a running scanLoop
  stream?.getTracks().forEach((t) => t.stop())
  stream = null
  scanning.value = false
}

async function scanLoop(id: number) {
  for (countdown.value = 5; countdown.value > 0; countdown.value--) {
    await new Promise((r) => setTimeout(r, 1000))
    if (id !== scanId) return
  }
  const frame = document.createElement('canvas')
  while (id === scanId) {
    const v = video.value
    if (!v?.videoWidth) {
      await new Promise((r) => setTimeout(r, 100)) // camera still starting
      continue
    }
    frame.width = v.videoWidth
    frame.height = v.videoHeight
    frame.getContext('2d')!.drawImage(v, 0, 0)
    try {
      const d = await detectNails(frame, conf.value[0] ?? 0.35)
      if (id !== scanId) return
      const n = d.nails.length
      steady.value = !n ? 0 : n === liveCount.value ? steady.value + 1 : 1
      liveCount.value = n
      if (overlay.value) drawDetections(overlay.value, frame, d, [], false)
      if (steady.value >= STEADY) {
        stopScan()
        frame.toBlob(
          (b) => b && load(b, `Scan ${new Date().toLocaleTimeString()}`),
          'image/jpeg',
          0.92,
        )
      }
    } catch (e) {
      error.value = e instanceof Error ? e.message : String(e)
      stopScan()
    }
  }
}

async function generate() {
  const d = det.value
  const nails = d ? d.nails.filter((x) => selected.value.includes(x.number)) : []
  if (!nails.length || !img || !d) return
  clearInterval(timer)
  error.value = ''
  designs.value = []
  generating.value = true
  progress.value = 0
  designStart = now.value = Date.now()
  genStatus.value = 'Sending the nails to the design service'
  try {
    const id = await startJob(
      await photoBlob(img!),
      await Promise.all(nails.map((n) => nailMaskBlob(img!, d, n))),
      colors.value,
      steps.value[0] ?? 30,
    )
    jobId.value = id
    const poll = async () => {
      try {
        const j = await getJob(id)
        if (j.designs.length !== designs.value.length) designStart = Date.now()
        designs.value = j.designs
        j.designs.forEach((d) => store.add(id, d))
        progress.value = j.progress ?? 0
        now.value = Date.now()
        genStatus.value =
          j.status === 'done'
            ? ''
            : `Painting design ${Math.min(5, j.designs.length + 1)} of 5 (${progress.value}%)`
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
    timer = window.setInterval(poll, 1500)
  } catch (e) {
    genStatus.value = ''
    generating.value = false
    service.value = 'offline'
    error.value =
      (e instanceof Error ? e.message : String(e)) +
      '. Check that the design service is running on port 8000.'
  }
}

const steps3 = computed(() => {
  const done = [
    hasPhoto.value,
    !!det.value?.nails.length,
    designs.value.length === 5 && !generating.value,
  ]
  const cur = done.indexOf(false)
  return ['Photo', 'Nails', 'Designs'].map((label, i) => ({
    label,
    done: done[i],
    current: i === cur,
  }))
})

const match = (de: number) =>
  de < 10
    ? { text: 'Close match', cls: 'text-success' }
    : de < 20
      ? { text: 'Same colour family', cls: 'text-warning' }
      : { text: 'Loose match', cls: 'text-muted-foreground' }

watch(selected, redraw)
onBeforeUnmount(() => {
  clearInterval(timer)
  stopScan()
})
onDeactivated(stopScan) // KeepAlive: release the camera when leaving the page
</script>

<template>
  <div>
    <div
      class="mb-8 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between bg-card/90 rounded-2xl p-4 backdrop-blur"
    >
      <div>
        <h1 class="font-display text-3xl font-extrabold tracking-tight sm:text-4xl">
          Try nail designs on your own hand
        </h1>
        <p class="text-muted-foreground mt-1.5 max-w-xl text-sm leading-relaxed">
          Scan your hand, pick up to three polishes, and get five designs painted on your nails.
        </p>
      </div>
      <ol class="flex items-center gap-2 text-xs font-medium" aria-label="Progress">
        <template v-for="(s, i) in steps3" :key="s.label">
          <li
            class="flex items-center gap-1.5 rounded-full border px-3 py-1.5 transition-colors"
            :class="
              s.done
                ? 'border-transparent bg-success/10 text-success'
                : s.current
                  ? 'border-primary bg-accent text-accent-foreground'
                  : 'text-muted-foreground'
            "
            :aria-current="s.current ? 'step' : undefined"
          >
            <Check v-if="s.done" class="size-3.5" /> {{ s.label }}
          </li>
          <span v-if="i < 2" class="bg-border h-px w-3 sm:w-5" aria-hidden="true" />
        </template>
      </ol>
    </div>
    <div class="grid gap-8 lg:grid-cols-[minmax(0,1fr)_360px]">
      <!-- stage -->
      <section aria-label="Hand photo" class="flex flex-col">
        <Card v-if="scanning" class="flex-1 overflow-hidden rounded-2xl shadow-sm">
          <div class="flex items-center gap-3 border-b px-4 py-3">
            <div class="min-w-0">
              <p class="text-sm font-semibold">Scanning</p>
              <p class="text-muted-foreground text-xs" role="status">
                <template v-if="countdown"
                  >Place your hand in the frame. Detecting in {{ countdown }}s…</template
                >
                <template v-else-if="!liveCount"
                  >Looking for nails. Fit your hand inside the frame.</template
                >
                <template v-else>
                  {{ liveCount }} {{ liveCount === 1 ? 'nail' : 'nails' }} found. Hold still…
                </template>
              </p>
            </div>
            <Button variant="outline" size="sm" class="ml-auto" @click="stopScan">
              <X /> Cancel
            </Button>
          </div>
          <div class="bg-black">
            <div class="relative mx-auto max-w-[640px] overflow-hidden">
              <video
                ref="video"
                autoplay
                playsinline
                muted
                class="aspect-square w-full object-cover"
              />
              <!-- same size and crop as the video, so the boxes sit on the nails -->
              <canvas
                ref="overlay"
                class="pointer-events-none absolute inset-0 size-full object-cover"
                aria-hidden="true"
              />
              <div class="pointer-events-none absolute inset-0" aria-hidden="true">
                <span class="scan-frame" />
                <span v-if="!countdown" class="scan-line" />
                <Transition name="fade" mode="out-in">
                  <span
                    v-if="countdown"
                    :key="countdown"
                    class="font-display absolute inset-0 grid place-items-center text-8xl font-extrabold text-white drop-shadow-lg"
                    >{{ countdown }}</span
                  >
                </Transition>
              </div>
            </div>
          </div>
          <!-- fills as the nails hold steady; full = photo taken -->
          <div class="bg-muted h-1.5" aria-hidden="true">
            <div
              class="bg-primary h-full transition-all duration-300"
              :style="{ width: `${(Math.min(steady, STEADY) / STEADY) * 100}%` }"
            />
          </div>
        </Card>

        <div
          v-else-if="!hasPhoto"
          class="bg-card flex min-h-[460px] flex-1 flex-col items-center justify-center gap-4 rounded-2xl border-2 border-dashed p-8 text-center"
        >
          <span
            class="bg-accent text-primary flex size-14 items-center justify-center rounded-full"
          >
            <ScanLine class="size-6" />
          </span>
          <span class="font-display text-2xl font-bold tracking-tight">Scan your hand</span>
          <span class="text-muted-foreground max-w-sm text-sm leading-relaxed">
            Lay your hand flat, nails facing the camera, in even light. NailVision finds each nail
            and numbers it from left to right.
          </span>
          <Button size="lg" @click="startScan"><ScanLine /> Start scan</Button>
          <span class="text-muted-foreground text-xs">
            The photo is taken automatically once your nails are found.
          </span>
        </div>

        <Card v-else class="flex-1 overflow-hidden rounded-2xl shadow-sm">
          <div class="flex items-center gap-3 border-b px-4 py-3">
            <div class="min-w-0">
              <p class="truncate text-sm font-semibold">{{ photoName }}</p>
              <p class="text-muted-foreground text-xs">
                <template v-if="busy">Scanning nails…</template>
                <template v-else-if="det">
                  {{ det.nails.length }} {{ det.nails.length === 1 ? 'nail' : 'nails' }} found in
                  {{ det.ms.toFixed(0) }} ms
                </template>
              </p>
            </div>
            <Button variant="outline" size="sm" class="ml-auto" @click="startScan">
              <ScanLine /> Rescan
            </Button>
          </div>
          <div class="bg-muted/50 relative p-3">
            <canvas
              ref="canvas"
              class="mx-auto aspect-square w-full max-w-[640px] rounded-lg object-contain"
            />
            <Transition name="fade">
              <div
                v-if="busy"
                class="bg-background/30 absolute inset-3 flex items-end justify-center overflow-hidden rounded-lg pb-4"
                role="status"
              >
                <span class="scan-line" aria-hidden="true" />
                <span
                  class="bg-card/95 relative flex items-center gap-2 rounded-full border px-4 py-2 text-sm font-medium shadow"
                >
                  <Loader class="text-primary size-4 animate-spin" /> Scanning for nails…
                </span>
              </div>
            </Transition>
          </div>
        </Card>

        <p
          v-if="error"
          role="alert"
          class="border-destructive/40 bg-card text-destructive mt-4 rounded-lg border p-3 text-sm"
        >
          {{ error }}
        </p>
      </section>

      <!-- controls -->
      <aside class="flex flex-col" aria-label="Design controls">
        <Card class="flex-1 p-5">
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

          <h2 class="font-display mt-5 border-t pt-5 text-base font-bold">Polishes</h2>
          <p class="text-muted-foreground mt-1 text-xs leading-relaxed">
            Each of the first three designs uses one of these as its base. Every design is applied
            to all detected nails (up to 5).
          </p>
          <!-- chosen palette, shown as one strip so the colours are easy to compare -->
          <div
            class="mt-3 flex h-8 overflow-hidden rounded-lg border-2 border-foreground/30"
            role="img"
            :aria-label="`Chosen palette: ${colors.join(', ')}`"
          >
            <span v-for="(c, i) in colors" :key="i" class="flex-1" :style="{ background: c }" />
          </div>
          <div class="mt-3 flex gap-3">
            <label
              v-for="(_, i) in colors"
              :key="i"
              class="flex flex-1 cursor-pointer flex-col gap-1.5 text-xs"
            >
              <span
                class="focus-within:ring-ring/50 border-foreground/30 relative block h-16 overflow-hidden rounded-lg border-2 shadow-sm focus-within:ring-[3px]"
                :style="{ background: colors[i] }"
              >
                <input
                  v-model="colors[i]"
                  type="color"
                  class="absolute inset-0 size-full cursor-pointer opacity-0"
                  :aria-label="`Polish ${i + 1}`"
                />
                <span
                  class="bg-card/90 text-foreground absolute right-1 bottom-1 grid size-6 place-items-center rounded-full shadow"
                  aria-hidden="true"
                >
                  <Pipette class="size-3.5" />
                </span>
              </span>
              <span class="text-foreground text-center font-medium tabular-nums uppercase">
                Polish {{ i + 1 }}<br /><span class="text-muted-foreground font-normal">{{
                  colors[i]
                }}</span>
              </span>
            </label>
          </div>

          <fieldset class="mt-5 border-t pt-4">
            <legend class="text-sm font-medium">Design quality</legend>
            <div class="mt-3 grid grid-cols-3 gap-2">
              <label
                v-for="q in qualities"
                :key="q.steps"
                class="border-input has-[:checked]:border-primary has-[:checked]:bg-accent has-[:checked]:text-accent-foreground has-[:focus-visible]:ring-ring/50 cursor-pointer rounded-lg border-2 p-2 text-center transition-colors has-[:focus-visible]:ring-[3px]"
              >
                <input
                  v-model="steps[0]"
                  type="radio"
                  name="quality"
                  :value="q.steps"
                  class="sr-only"
                />
                <span class="block text-sm font-semibold">{{ q.name }}</span>
                <span class="text-muted-foreground block text-xs">{{ q.hint }}</span>
              </label>
            </div>
          </fieldset>

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
            Scan a hand with visible nails first.
          </p>
          <p v-if="genStatus" role="status" class="text-muted-foreground mt-3 text-center text-xs">
            {{ genStatus }}.
            {{
              fast
                ? 'The GPU makes each design quick.'
                : 'On a CPU each design takes a few minutes.'
            }}
          </p>
        </Card>
      </aside>
    </div>

    <!-- results -->
    <section class="mt-12" aria-label="Designs">
      <div class="flex items-end justify-between bg-card/90 rounded-2xl p-4 backdrop-blur">
        <div>
          <h2 class="font-display text-2xl font-bold tracking-tight">Designs</h2>
          <p class="text-muted-foreground text-sm">
            Three use your polishes. Two are suggestions we picked. Each appears as soon as it is
            finished.
          </p>
        </div>
      </div>
      <div v-if="generating" class="bg-card mt-5 rounded-xl border p-4 shadow-sm" role="status">
        <div class="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 text-sm">
          <span class="font-semibold">
            Design {{ Math.min(5, designs.length + 1) }} of 5
            <span class="text-muted-foreground font-normal tabular-nums">· {{ progress }}%</span>
          </span>
          <span class="text-muted-foreground tabular-nums">
            {{ perDesign ? `${fmt(left)} left` : 'Estimating time…' }}
          </span>
        </div>
        <div
          class="bg-muted mt-3 h-2 overflow-hidden rounded-full"
          role="progressbar"
          aria-label="Overall progress"
          aria-valuemin="0"
          aria-valuemax="100"
          :aria-valuenow="overall"
        >
          <div
            class="bg-primary h-full rounded-full transition-all"
            :style="{ width: `${overall}%` }"
          />
        </div>
        <p class="text-muted-foreground mt-2 text-xs">
          {{ overall }}% of all 5 designs. Each design is shown the moment it finishes.
        </p>
      </div>
      <p
        v-if="!designs.length && !pending"
        class="text-muted-foreground bg-card/90 mt-5 rounded-2xl border-2 border-dashed p-8 text-center text-sm"
      >
        Your five designs will appear here. Scan your hand, then choose Generate 5 designs.
      </p>
      <!-- one row of 5: cards shrink to fit, and the row scrolls sideways on narrow screens -->
      <div class="mt-5 grid auto-cols-[minmax(11rem,1fr)] grid-flow-col gap-3 overflow-x-auto pb-2">
        <Card
          v-for="d in designs"
          :key="d.slot"
          class="hover:shadow-card overflow-hidden rounded-xl shadow-sm transition-shadow"
        >
          <button
            type="button"
            class="focus-visible:ring-ring/50 block w-full cursor-zoom-in outline-none focus-visible:ring-[3px]"
            :aria-label="`View ${d.style} design full screen`"
            @click="view = `data:image/jpeg;base64,${d.full_jpeg_b64}`"
          >
            <img
              :src="`data:image/jpeg;base64,${d.zoom_jpeg_b64}`"
              :alt="`${d.style} design on nails ${selected.join(', ')}`"
              class="bg-muted aspect-square w-full object-contain"
            />
          </button>
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
                class="size-4 rounded-full ring-1 ring-foreground/30"
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
            <StarRating
              :model-value="store.get(`${jobId}-${d.slot}`)?.rating ?? 0"
              :label="`Rate ${d.style} design`"
              @update:model-value="store.rate(`${jobId}-${d.slot}`, $event)"
            />
            <Button size="sm" @click="booking = store.get(`${jobId}-${d.slot}`) ?? null">
              <CalendarCheck /> Book at a salon
            </Button>
          </div>
        </Card>

        <Card
          v-for="k in pending"
          :key="`s${k}`"
          class="overflow-hidden rounded-xl"
          aria-hidden="true"
        >
          <div class="bg-muted relative aspect-square w-full animate-pulse">
            <span v-if="k === 1" class="absolute inset-0 grid place-items-center text-lg font-bold">
              {{ progress }}%
            </span>
          </div>
          <div class="flex flex-col gap-2 p-3">
            <template v-if="k === 1">
              <div class="bg-muted h-1.5 overflow-hidden rounded">
                <div class="bg-primary h-full transition-all" :style="{ width: `${progress}%` }" />
              </div>
              <p class="text-muted-foreground text-xs tabular-nums">
                Painting ·
                {{ perDesign ? `${fmt(perDesign * (1 - progress / 100))} left` : 'estimating…' }}
              </p>
            </template>
            <p v-else class="text-muted-foreground text-xs">
              Queued{{ perDesign ? ` · ~${Math.ceil(perDesign / 60)} min each` : '' }}
            </p>
            <div class="bg-muted h-3 w-1/2 animate-pulse rounded" />
          </div>
        </Card>
      </div>
    </section>

    <ImageViewer :src="view" alt="Design in full screen" @close="view = null" />
    <BookDialog :design="booking" @close="booking = null" />
  </div>
</template>
