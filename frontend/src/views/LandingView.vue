<script setup lang="ts">
import { RouterLink } from 'vue-router'
import type { Directive } from 'vue'
import {
  Camera,
  ScanSearch,
  Palette,
  Sparkles,
  CalendarCheck,
  ShieldCheck,
  Check,
  Download,
  Smartphone,
} from 'lucide-vue-next'
import { Capacitor } from '@capacitor/core'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import PolishNails from '@/components/PolishNails.vue'
import StarRating from '@/components/StarRating.vue'

// fades an element up the first time it scrolls into view; --d on the element staggers siblings
const seen = new WeakMap<Element, IntersectionObserver>()
const vScrollIn: Directive<HTMLElement> = {
  mounted(el) {
    el.classList.add('scroll-in')
    const io = new IntersectionObserver(
      ([e]) => {
        if (!e?.isIntersecting) return
        el.classList.add('shown')
        io.disconnect()
      },
      { threshold: 0.15, rootMargin: '0px 0px -8% 0px' },
    )
    io.observe(el)
    seen.set(el, io)
  },
  unmounted: (el) => seen.get(el)?.disconnect(),
}

const steps = [
  {
    icon: Camera,
    title: 'Add a hand photo',
    text: 'Nails facing the camera in even light work best.',
  },
  {
    icon: ScanSearch,
    title: 'Check your nails',
    text: 'Up to five nails are found and numbered left to right, right in your browser.',
  },
  {
    icon: Palette,
    title: 'Pick three polishes',
    text: 'Choose your colors from the swatches. The strip shows the whole palette at once.',
  },
  {
    icon: Sparkles,
    title: 'Generate five designs',
    text: 'Each design appears the moment it is ready. Keep browsing while the rest are painted.',
  },
  {
    icon: CalendarCheck,
    title: 'Book a salon',
    text: 'Rate your favorites and send one to a salon for a nail technician to review.',
  },
]

const designs = [
  { colors: ['#b8305c', '#f27b9d', '#e9b8a7'], mine: true },
  { colors: ['#e9b8a7', '#b8305c', '#f27b9d'], mine: true },
  { colors: ['#f27b9d', '#e9b8a7', '#b8305c'], mine: true },
  { colors: ['#0b1f55', '#9fb4e8', '#ece9f6'], mine: false },
  { colors: ['#7a1f3d', '#d9a441', '#2f2a26'], mine: false },
]

const qualities = [
  { name: 'Quick', text: 'A fast preview that looks a little rougher.' },
  { name: 'Balanced', text: 'The right choice for most photos.' },
  { name: 'Best', text: 'The finest result. Takes the longest.' },
]

const statuses = ['Waiting for review', 'Accepted', 'Needs changes', 'Done']

// no point offering the app download inside the app itself
const isApp = Capacitor.isNativePlatform()
const apkUrl = `${import.meta.env.BASE_URL}downloads/NailVision.apk`
</script>

<template>
  <div class="flex flex-col gap-20 sm:gap-28">
    <!-- hero: the painted hand is the one moment that plays on load -->
    <section
      class="bg-card/90 grid items-center gap-10 overflow-hidden rounded-3xl border p-6 backdrop-blur sm:p-12 lg:grid-cols-[1.25fr_1fr]"
      aria-labelledby="hero-title"
    >
      <div class="flex flex-col items-start gap-5">
        <h1
          id="hero-title"
          class="font-display max-w-[14ch] text-4xl leading-[1.02] font-extrabold tracking-tight text-balance sm:text-6xl"
        >
          Try five nail designs on your own hand.
        </h1>
        <p class="text-muted-foreground max-w-[46ch] text-base leading-relaxed sm:text-lg">
          Take a photo, pick three polishes, and NailVision paints five designs right onto your
          nails. Send the one you love to a salon and get a nail technician's honest take before
          your appointment.
        </p>
        <div class="flex flex-wrap gap-3">
          <Button as-child size="lg"
            ><RouterLink :to="{ name: 'login', query: { mode: 'up' } }"
              >Create an account</RouterLink
            ></Button
          >
          <Button as-child size="lg" variant="outline"
            ><RouterLink :to="{ name: 'login', query: { mode: 'in' } }">Sign in</RouterLink></Button
          >
        </div>
      </div>
      <div class="bg-accent grid place-items-center rounded-2xl px-6 py-10 sm:py-14">
        <PolishNails :scale="1.9" class="max-sm:hidden" />
        <PolishNails :scale="1.4" class="sm:hidden" />
      </div>
    </section>

    <!-- a real sequence, so the steps are numbered -->
    <section aria-labelledby="how-title">
      <div v-scroll-in class="bg-card/90 max-w-2xl rounded-2xl p-5 backdrop-blur sm:p-6">
        <h2 id="how-title" class="font-display text-3xl font-extrabold tracking-tight sm:text-4xl">
          From one photo to a booked set
        </h2>
        <p class="text-muted-foreground mt-2">Everything happens in the Studio, in five steps.</p>
      </div>
      <ol class="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <li
          v-for="(s, i) in steps"
          :key="s.title"
          v-scroll-in
          :style="{ '--d': i }"
          class="bg-card flex flex-col gap-3 rounded-2xl border p-5"
        >
          <div class="flex items-center justify-between">
            <span class="font-display text-primary text-3xl font-extrabold tabular-nums">{{
              i + 1
            }}</span>
            <component :is="s.icon" class="text-muted-foreground size-5" aria-hidden="true" />
          </div>
          <h3 class="font-display text-lg leading-tight font-bold">{{ s.title }}</h3>
          <p class="text-muted-foreground text-sm leading-relaxed">{{ s.text }}</p>
        </li>
      </ol>
    </section>

    <section
      class="bg-card/90 grid gap-10 rounded-3xl border p-6 backdrop-blur sm:p-12 lg:grid-cols-[1fr_1.1fr]"
      aria-labelledby="designs-title"
    >
      <div v-scroll-in class="flex flex-col gap-4">
        <h2
          id="designs-title"
          class="font-display text-3xl font-extrabold tracking-tight sm:text-4xl"
        >
          Five designs from one photo
        </h2>
        <p class="text-muted-foreground max-w-[52ch] leading-relaxed">
          The first three use the polishes you picked, each with a score for how closely the result
          matches your colors. The last two are palettes chosen for you, for when you want to try
          something new.
        </p>
        <dl class="mt-2 flex flex-col gap-3">
          <div v-for="q in qualities" :key="q.name" class="flex gap-3 border-t pt-3 text-sm">
            <dt class="w-20 shrink-0 font-semibold">{{ q.name }}</dt>
            <dd class="text-muted-foreground">{{ q.text }}</dd>
          </div>
        </dl>
      </div>
      <ul class="grid grid-cols-2 gap-3 self-center sm:grid-cols-3">
        <li
          v-for="(d, i) in designs"
          :key="i"
          v-scroll-in
          :style="{ '--d': i }"
          class="bg-background overflow-hidden rounded-xl border"
        >
          <div class="flex aspect-[3/4]">
            <span v-for="c in d.colors" :key="c" class="flex-1" :style="{ background: c }" />
          </div>
          <div class="p-2.5">
            <p class="text-xs font-semibold">{{ d.mine ? 'Your polishes' : 'Suggested' }}</p>
            <p class="text-xs" :class="d.mine ? 'text-success' : 'text-muted-foreground'">
              {{ d.mine ? 'Close match' : 'Random palette' }}
            </p>
          </div>
        </li>
      </ul>
    </section>

    <section
      v-scroll-in
      class="bg-accent text-accent-foreground flex flex-col gap-4 rounded-3xl p-6 sm:flex-row sm:items-center sm:gap-8 sm:p-10"
      aria-labelledby="privacy-title"
    >
      <span
        class="bg-card text-primary grid size-14 shrink-0 place-items-center rounded-2xl border"
      >
        <ShieldCheck class="size-7" aria-hidden="true" />
      </span>
      <div>
        <h2 id="privacy-title" class="font-display text-2xl font-extrabold tracking-tight">
          Your nails are found on your device
        </h2>
        <p class="mt-1.5 max-w-[65ch] text-sm leading-relaxed opacity-80">
          NailVision spots and numbers your nails right in the browser. Your photo only goes to the
          design service when you choose Generate, so it can paint the designs. Saved designs stay
          in your browser until you book one.
        </p>
      </div>
    </section>

    <section class="grid items-center gap-10 lg:grid-cols-[1fr_1fr]" aria-labelledby="tech-title">
      <div v-scroll-in class="bg-card/90 flex flex-col gap-4 rounded-2xl p-6 backdrop-blur sm:p-8">
        <h2 id="tech-title" class="font-display text-3xl font-extrabold tracking-tight sm:text-4xl">
          For nail technicians
        </h2>
        <p class="text-muted-foreground leading-relaxed">
          Sign up with your salon's name and every design a client sends you lands in one list. Tell
          them early whether it works, so the appointment starts with a plan.
        </p>
        <ul class="flex flex-col gap-2 text-sm">
          <li class="flex gap-2">
            <Check class="text-primary mt-0.5 size-4 shrink-0" aria-hidden="true" />See the design,
            palette and the client's note
          </li>
          <li class="flex gap-2">
            <Check class="text-primary mt-0.5 size-4 shrink-0" aria-hidden="true" />Mark it
            accepted, needs changes or done
          </li>
          <li class="flex gap-2">
            <Check class="text-primary mt-0.5 size-4 shrink-0" aria-hidden="true" />Rate whether it
            is worth doing and leave advice
          </li>
        </ul>
        <Button as-child class="self-start"
          ><RouterLink :to="{ name: 'login', query: { mode: 'up' } }"
            >Register your salon</RouterLink
          ></Button
        >
      </div>

      <!-- sample review, built from the same parts as the real Design reviews page -->
      <figure
        v-scroll-in
        :style="{ '--d': 1 }"
        class="bg-card flex flex-col gap-3 rounded-2xl border p-5 shadow-card"
        aria-label="Example of a design review"
      >
        <div class="flex flex-wrap gap-1.5">
          <Badge v-for="(s, i) in statuses" :key="s" :variant="i === 1 ? 'default' : 'outline'">{{
            s
          }}</Badge>
        </div>
        <div class="flex items-center gap-3">
          <div class="flex h-14 w-12 overflow-hidden rounded-lg">
            <span
              v-for="c in designs[0]!.colors"
              :key="c"
              class="flex-1"
              :style="{ background: c }"
            />
          </div>
          <div>
            <p class="font-display font-bold">Soft ombré</p>
            <p class="text-muted-foreground text-xs">From a client at your salon</p>
          </div>
        </div>
        <p class="bg-muted rounded-lg p-2.5 text-xs">“Can the tips be a little shorter?”</p>
        <div class="flex items-center gap-2 text-xs">
          Worth it?
          <StarRating :model-value="4" readonly label="Technician rating" />
        </div>
        <p class="bg-accent rounded-lg p-2.5 text-xs">
          Doable in about an hour. I'd keep the tips short and go one shade lighter on the base.
        </p>
      </figure>
    </section>

    <section
      v-if="!isApp"
      v-scroll-in
      class="bg-card/90 flex flex-col gap-5 rounded-3xl border p-6 backdrop-blur sm:flex-row sm:items-center sm:justify-between sm:p-10"
      aria-labelledby="app-title"
    >
      <div class="flex items-start gap-4">
        <span
          class="bg-accent text-primary grid size-14 shrink-0 place-items-center rounded-2xl border"
        >
          <Smartphone class="size-7" aria-hidden="true" />
        </span>
        <div>
          <h2 id="app-title" class="font-display text-2xl font-extrabold tracking-tight">
            Get the NailVision app
          </h2>
          <p class="text-muted-foreground mt-1.5 max-w-[55ch] text-sm leading-relaxed">
            Install it on your Android phone. You may need to allow installs from your browser.
          </p>
        </div>
      </div>
      <Button as-child size="lg"
        ><a :href="apkUrl" download="NailVision.apk"
          ><Download aria-hidden="true" />Download for Android</a
        ></Button
      >
    </section>

    <section
      v-scroll-in
      class="bg-primary text-primary-foreground flex flex-col items-start gap-5 rounded-3xl p-8 sm:flex-row sm:items-center sm:justify-between sm:p-12"
      aria-labelledby="cta-title"
    >
      <div>
        <h2 id="cta-title" class="font-display text-3xl font-extrabold tracking-tight sm:text-4xl">
          Your next set starts with a photo.
        </h2>
        <p class="mt-2 opacity-85">Create an account and open the Studio.</p>
      </div>
      <Button as-child size="lg" variant="secondary"
        ><RouterLink :to="{ name: 'login', query: { mode: 'up' } }"
          >Create an account</RouterLink
        ></Button
      >
    </section>
  </div>
</template>

<style scoped>
.scroll-in {
  opacity: 0;
  transform: translateY(28px);
  transition:
    opacity 0.7s cubic-bezier(0.22, 1, 0.36, 1),
    transform 0.8s cubic-bezier(0.22, 1, 0.36, 1);
  transition-delay: calc(var(--d, 0) * 90ms);
}
.scroll-in.shown {
  opacity: 1;
  transform: none;
}
@media (prefers-reduced-motion: reduce) {
  .scroll-in {
    opacity: 1;
    transform: none;
  }
}
</style>
