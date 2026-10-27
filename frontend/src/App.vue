<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink, RouterView, useRouter } from 'vue-router'
import {
  RefreshCw,
  LogOut,
  Loader,
  LayoutDashboard,
  Sparkles,
  Images,
  CalendarCheck,
  ClipboardCheck,
} from 'lucide-vue-next'
import { Badge } from '@/components/ui/badge'
import { service, deviceLabel, refreshService } from '@/lib/service'
import { useAuth } from '@/stores/auth'
import logo from '@/assets/logo.png'
import bg from '@/assets/pic1.jpg'

const auth = useAuth()
const router = useRouter()
const nav = computed(() =>
  auth.profile?.role === 'technician'
    ? [{ to: '/tech', label: 'Design reviews', short: 'Reviews', icon: ClipboardCheck }]
    : auth.profile
      ? [
          { to: '/client', label: 'Dashboard', short: 'Home', icon: LayoutDashboard },
          { to: '/client/studio', label: 'Studio', short: 'Studio', icon: Sparkles },
          { to: '/client/history', label: 'Previous designs', short: 'Designs', icon: Images },
          { to: '/client/bookings', label: 'My bookings', short: 'Bookings', icon: CalendarCheck },
        ]
      : [],
)
const tabBar = computed(() => nav.value.length > 1) // one destination needs no tab bar
async function signOut() {
  auth.busy = true
  try {
    await auth.signOut()
    await router.replace('/login')
  } finally {
    auth.busy = false
  }
}

// top bar: creeps toward 85% while busy, then fills and fades once the next page is shown
const bar = ref<'idle' | 'run' | 'done'>('idle')
const leaving = ref(false) // fixed when busy starts: profile flips mid sign-in
let hide: ReturnType<typeof setTimeout>
watch(
  () => auth.busy,
  (on) => {
    clearTimeout(hide)
    if (on) leaving.value = !!auth.profile
    bar.value = on ? 'run' : 'done'
    if (!on) hide = setTimeout(() => (bar.value = 'idle'), 500)
  },
)
onMounted(refreshService)
</script>

<template>
  <div
    class="flex min-h-screen flex-col lg:pb-0"
    :class="tabBar && 'pb-[calc(4rem+env(safe-area-inset-bottom))]'"
  >
    <div class="auth-bar" :class="bar" aria-hidden="true" />
    <Transition name="fade">
      <div
        v-if="auth.busy"
        class="bg-background/70 fixed inset-0 z-40 grid place-items-center backdrop-blur-sm"
        role="status"
        aria-live="polite"
      >
        <div
          class="bg-card flex flex-col items-center gap-3 rounded-2xl border px-10 py-8 shadow-lg"
        >
          <span class="relative block size-14 overflow-hidden rounded-full border bg-[#fefcfa]">
            <img
              :src="logo"
              alt=""
              class="absolute max-w-none"
              style="width: 156px; left: -54px; top: -31px"
            />
          </span>
          <p class="flex items-center gap-2 text-sm font-medium">
            <Loader class="text-primary size-4 animate-spin" />
            {{ leaving ? 'Signing you out…' : 'Signing you in…' }}
          </p>
        </div>
      </div>
    </Transition>
    <div class="app-bg" aria-hidden="true" :style="{ backgroundImage: `url(${bg})` }" />
    <header class="bg-card/90 sticky top-0 z-20 border-b pt-[env(safe-area-inset-top)] backdrop-blur">
      <div
        class="mx-auto flex h-14 max-w-6xl items-center justify-between gap-4 px-4 sm:px-6 lg:grid lg:h-16 lg:grid-cols-[1fr_auto_1fr]"
      >
        <RouterLink
          to="/"
          aria-label="NailVision home"
          class="focus-visible:ring-ring/50 flex shrink-0 items-center gap-2.5 rounded-full outline-none focus-visible:ring-[3px]"
        >
          <!-- circular crop of the logo icon (nail + frame) -->
          <span class="relative block size-10 overflow-hidden rounded-full border bg-[#fefcfa]">
            <img
              :src="logo"
              alt=""
              class="absolute max-w-none"
              style="width: 112px; left: -39px; top: -22px"
            />
          </span>
          <span class="font-display text-xl font-extrabold tracking-tight"
            >Nail<span class="text-primary">Vision</span></span
          >
        </RouterLink>

        <!-- desktop tabs: centred column; the active one gets a nail-tip marker on the header rule -->
        <nav class="hidden h-full items-stretch gap-1 lg:flex" aria-label="Main">
          <RouterLink
            v-for="n in nav"
            :key="n.to"
            :to="n.to"
            class="text-muted-foreground hover:text-foreground focus-visible:ring-ring/50 aria-[current=page]:text-foreground after:bg-primary relative flex items-center px-3 text-sm font-medium whitespace-nowrap transition-colors outline-none after:absolute after:inset-x-3 after:-bottom-px after:h-[5px] after:origin-bottom after:scale-y-0 after:rounded-t-full after:transition-transform focus-visible:rounded-lg focus-visible:ring-[3px] focus-visible:ring-inset aria-[current=page]:after:scale-y-100 motion-reduce:after:transition-none"
          >
            {{ n.label }}
          </RouterLink>
        </nav>

        <div class="flex items-center justify-end gap-2">
          <button
            class="focus-visible:ring-ring/50 text-muted-foreground hover:text-foreground flex cursor-pointer items-center gap-2 rounded-full border px-2.5 py-1.5 text-xs font-medium whitespace-nowrap transition-colors outline-none focus-visible:ring-[3px] sm:px-3"
            :title="`Design service ${service}. Click to recheck.`"
            :aria-label="`Design service ${service}. Recheck`"
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
            <span class="hidden sm:inline">
              {{ service === 'online' ? 'Ready' : service === 'offline' ? 'Offline' : 'Checking' }}
              <span v-if="deviceLabel" class="hidden xl:inline">· {{ deviceLabel }}</span>
            </span>
            <RefreshCw class="hidden size-3 sm:block" />
          </button>
          <button
            v-if="auth.profile"
            class="focus-visible:ring-ring/50 text-muted-foreground hover:text-foreground flex cursor-pointer items-center gap-1.5 rounded-full border p-2 text-xs font-medium whitespace-nowrap transition-colors outline-none focus-visible:ring-[3px] sm:px-3 sm:py-1.5"
            :title="`Signed in as ${auth.profile.full_name || auth.profile.role}`"
            aria-label="Sign out"
            @click="signOut"
          >
            <LogOut class="size-3.5 sm:size-3" />
            <span class="hidden sm:inline">Sign out</span>
          </button>
        </div>
      </div>
    </header>

    <!-- phone tabs: bottom bar within thumb reach, clear of the gesture area -->
    <nav
      v-if="tabBar"
      class="bg-card/95 fixed inset-x-0 bottom-0 z-20 border-t pb-[env(safe-area-inset-bottom)] backdrop-blur lg:hidden"
      aria-label="Main"
    >
      <div class="mx-auto grid h-16 max-w-md grid-flow-col auto-cols-fr">
        <RouterLink
          v-for="n in nav"
          :key="n.to"
          :to="n.to"
          class="group text-muted-foreground aria-[current=page]:text-foreground focus-visible:ring-ring/50 flex flex-col items-center justify-center gap-1 text-[11px] font-medium outline-none focus-visible:rounded-lg focus-visible:ring-[3px] focus-visible:ring-inset"
        >
          <span
            class="group-aria-[current=page]:bg-accent group-aria-[current=page]:text-primary grid h-7 w-14 place-items-center rounded-[999px_999px_10px_10px] transition-colors"
          >
            <component :is="n.icon" class="size-[18px]" aria-hidden="true" />
          </span>
          {{ n.short }}
        </RouterLink>
      </div>
    </nav>

    <main class="mx-auto w-full max-w-6xl flex-1 px-4 py-8 pb-20 sm:px-6">
      <!-- KeepAlive: a running generation keeps going while you visit other pages -->
      <RouterView v-slot="{ Component }">
        <Transition name="page" mode="out-in">
          <KeepAlive><component :is="Component" /></KeepAlive>
        </Transition>
      </RouterView>
    </main>

    <footer class="text-muted-foreground bg-card border-t py-6 text-center text-xs">
      <Badge variant="outline">Detection on device</Badge>
      <span class="ml-2"
        >Nails are found in your browser. Your photo is sent to the design service to paint the
        designs.</span
      >
    </footer>
  </div>
</template>
