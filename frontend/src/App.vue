<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink, RouterView, useRouter } from 'vue-router'
import { RefreshCw, LogOut } from 'lucide-vue-next'
import { Badge } from '@/components/ui/badge'
import { service, deviceLabel, refreshService } from '@/lib/service'
import { useAuth } from '@/stores/auth'
import logo from '@/assets/logo.png'
import bg from '@/assets/pic1.jpg'

const auth = useAuth()
const router = useRouter()
const nav = computed(() =>
  auth.profile?.role === 'technician'
    ? [{ to: '/tech', label: 'Design reviews' }]
    : auth.profile
      ? [
          { to: '/client', label: 'Dashboard' },
          { to: '/client/studio', label: 'Studio' },
          { to: '/client/history', label: 'Previous designs' },
          { to: '/client/bookings', label: 'My bookings' },
        ]
      : [],
)
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
let hide: ReturnType<typeof setTimeout>
watch(
  () => auth.busy,
  (on) => {
    clearTimeout(hide)
    bar.value = on ? 'run' : 'done'
    if (!on) hide = setTimeout(() => (bar.value = 'idle'), 500)
  },
)
onMounted(refreshService)
</script>

<template>
  <div class="flex min-h-screen flex-col">
    <div class="auth-bar" :class="bar" aria-hidden="true" />
    <div class="app-bg" aria-hidden="true" :style="{ backgroundImage: `url(${bg})` }" />
    <header class="bg-card sticky top-0 z-10 border-b">
      <div class="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-2 sm:px-6">
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

        <nav
          class="order-3 -mx-1 flex w-full gap-1 overflow-x-auto sm:order-none sm:mx-0 sm:w-auto"
          aria-label="Main"
        >
          <RouterLink
            v-for="n in nav"
            :key="n.to"
            :to="n.to"
            class="text-muted-foreground hover:text-foreground focus-visible:ring-ring/50 rounded-lg px-3 py-1.5 text-sm font-medium whitespace-nowrap transition-colors outline-none focus-visible:ring-[3px]"
            exact-active-class="!bg-accent !text-accent-foreground"
          >
            {{ n.label }}
          </RouterLink>
        </nav>

        <button
          class="focus-visible:ring-ring/50 text-muted-foreground hover:text-foreground ml-auto flex cursor-pointer items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-medium transition-colors outline-none focus-visible:ring-[3px]"
          title="Recheck the design service"
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
          <template v-if="deviceLabel">· {{ deviceLabel }}</template>
          <RefreshCw class="size-3" />
        </button>
        <button
          v-if="auth.profile"
          class="focus-visible:ring-ring/50 text-muted-foreground hover:text-foreground flex cursor-pointer items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium transition-colors outline-none focus-visible:ring-[3px]"
          :title="`Signed in as ${auth.profile.full_name || auth.profile.role}`"
          @click="signOut"
        >
          <LogOut class="size-3" /> Sign out
        </button>
      </div>
    </header>

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
