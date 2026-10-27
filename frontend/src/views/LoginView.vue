<script setup lang="ts">
import { ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { ArrowLeft, Eye, EyeOff } from 'lucide-vue-next'
import { Card } from '@/components/ui/card'
import PolishNails from '@/components/PolishNails.vue'
import { Button } from '@/components/ui/button'
import { useAuth } from '@/stores/auth'
import { cn } from '@/lib/utils'
import type { Profile } from '@/lib/supabase'

const auth = useAuth()
const router = useRouter()
const route = useRoute()
const mode = ref<'in' | 'up'>('in')
const username = ref('')
const password = ref('')
const showPassword = ref(false)
const fullName = ref('')
const role = ref<Profile['role']>('client')
const companyName = ref('')
const companyAddress = ref('')
const error = ref('')

// the landing page links here with ?mode=up to open on sign-up
watch(
  () => route.query.mode,
  (m) => m && (mode.value = m === 'up' ? 'up' : 'in'),
  { immediate: true },
)

function switchMode() {
  mode.value = mode.value === 'in' ? 'up' : 'in'
  error.value = ''
}

async function submit() {
  auth.busy = true
  error.value = ''
  try {
    if (mode.value === 'in') await auth.signIn(username.value, password.value)
    else {
      const meta = {
        role: role.value,
        full_name: fullName.value,
        ...(role.value === 'technician' && {
          company_name: companyName.value,
          company_address: companyAddress.value,
        }),
      }
      await auth.signUp(username.value, password.value, meta)
    }
    password.value = '' // KeepAlive keeps this page in memory after sign-in
    await router.replace('/')
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    auth.busy = false
  }
}

const field =
  'bg-background focus-visible:ring-ring/50 mt-1 w-full rounded-lg border px-3 py-2 text-sm font-normal outline-none focus-visible:ring-[3px]'
</script>

<template>
  <Card class="mx-auto grid max-w-4xl overflow-hidden md:grid-cols-[1.1fr_1fr]">
    <aside class="bg-accent flex flex-col justify-end gap-3 p-6 sm:p-10">
      <PolishNails class="mb-4" />
      <h1
        class="font-display max-w-[16ch] text-3xl leading-[1.05] font-extrabold tracking-tight text-balance sm:text-4xl"
      >
        See the design on your nails before you book.
      </h1>
      <p class="text-muted-foreground max-w-[40ch] text-sm leading-relaxed">
        Take a photo of your hand, get five designs, and send the one you like to a salon. Nail
        technicians review the designs clients send to their salon.
      </p>
    </aside>

    <section class="p-6 sm:p-10" aria-labelledby="login-title">
      <Button as-child variant="ghost" size="sm" class="text-muted-foreground mb-4 -ml-3.5">
        <RouterLink to="/"><ArrowLeft /> Back to home</RouterLink>
      </Button>
      <Transition name="swap" mode="out-in">
        <h2
          id="login-title"
          :key="mode"
          class="font-display text-2xl font-extrabold tracking-tight"
        >
          {{ mode === 'in' ? 'Sign in' : 'Create an account' }}
        </h2>
      </Transition>

      <form class="mt-6 flex flex-col gap-3" @submit.prevent="submit">
        <!-- sign-up fields stay in the page and slide open; disabled while closed so they are not validated -->
        <fieldset
          class="reveal min-w-0"
          :class="{ open: mode === 'up' }"
          :disabled="mode === 'in'"
          :inert="mode === 'in'"
        >
          <div class="flex flex-col gap-3">
            <div class="flex rounded-lg border p-0.5" role="radiogroup" aria-label="I am a">
              <label
                v-for="r in ['client', 'technician'] as const"
                :key="r"
                class="flex-1 cursor-pointer rounded-md px-3 py-1.5 text-center text-sm font-medium transition-colors has-[:focus-visible]:ring-[3px]"
                :class="
                  role === r
                    ? 'bg-primary text-primary-foreground'
                    : 'text-muted-foreground hover:text-foreground'
                "
              >
                <input v-model="role" type="radio" :value="r" class="sr-only" />
                {{ r === 'client' ? 'Client' : 'Nail technician' }}
              </label>
            </div>
            <label class="text-sm font-medium"
              >Full name <input v-model="fullName" required :class="field" autocomplete="name"
            /></label>
            <fieldset
              class="reveal at-end min-w-0"
              :class="{ open: role === 'technician' }"
              :disabled="role !== 'technician'"
              :inert="role !== 'technician'"
            >
              <div class="flex flex-col gap-3">
                <label class="text-sm font-medium"
                  >Salon name
                  <input
                    v-model="companyName"
                    required
                    maxlength="100"
                    :class="field"
                    autocomplete="organization"
                /></label>
                <label class="text-sm font-medium"
                  >Salon address (optional)
                  <input
                    v-model="companyAddress"
                    maxlength="200"
                    :class="field"
                    autocomplete="street-address"
                /></label>
              </div>
            </fieldset>
          </div>
        </fieldset>

        <label class="text-sm font-medium"
          >Username
          <input
            v-model="username"
            required
            minlength="3"
            maxlength="32"
            pattern="[A-Za-z0-9._\-]+"
            title="Letters, numbers, dots, dashes or underscores"
            :class="field"
            autocomplete="username"
            autocapitalize="none"
            spellcheck="false"
        /></label>
        <div>
          <label class="text-sm font-medium" for="login-password">Password</label>
          <div class="relative mt-1">
            <input
              id="login-password"
              v-model="password"
              :type="showPassword ? 'text' : 'password'"
              required
              minlength="6"
              :class="cn(field, 'mt-0 pr-10')"
              :autocomplete="mode === 'in' ? 'current-password' : 'new-password'"
            />
            <button
              type="button"
              class="text-muted-foreground hover:text-foreground focus-visible:ring-ring/50 absolute top-1/2 right-1 grid size-8 -translate-y-1/2 cursor-pointer place-items-center rounded-md outline-none focus-visible:ring-[3px]"
              :aria-label="showPassword ? 'Hide password' : 'Show password'"
              :aria-pressed="showPassword"
              @click="showPassword = !showPassword"
            >
              <EyeOff v-if="showPassword" class="size-4" />
              <Eye v-else class="size-4" />
            </button>
          </div>
        </div>

        <p v-if="error" class="text-destructive text-sm" role="alert">{{ error }}</p>
        <Button type="submit" class="mt-2" :disabled="auth.busy">
          {{
            auth.busy
              ? mode === 'in'
                ? 'Signing in…'
                : 'Creating account…'
              : mode === 'in'
                ? 'Sign in'
                : 'Create account'
          }}
        </Button>
      </form>

      <p class="text-muted-foreground mt-5 text-sm">
        {{ mode === 'in' ? 'New here?' : 'Already have an account?' }}
        <button
          type="button"
          class="text-primary focus-visible:ring-ring/50 cursor-pointer rounded font-medium underline underline-offset-2 outline-none focus-visible:ring-[3px]"
          @click="switchMode"
        >
          {{ mode === 'in' ? 'Create an account' : 'Sign in' }}
        </button>
      </p>
    </section>
  </Card>
</template>

<style scoped>
/* height animates through grid rows 0fr -> 1fr; the negative margin cancels the form gap while closed */
.reveal {
  display: grid;
  grid-template-rows: 0fr;
  margin-bottom: -0.75rem;
  opacity: 0;
  transition:
    grid-template-rows 0.35s cubic-bezier(0.22, 1, 0.36, 1),
    margin 0.35s cubic-bezier(0.22, 1, 0.36, 1),
    opacity 0.2s ease;
}
.reveal.open {
  grid-template-rows: 1fr;
  margin-bottom: 0;
  opacity: 1;
}
.reveal.at-end {
  /* last in its group: the gap to cancel sits above it */
  margin-bottom: 0;
  margin-top: -0.75rem;
}
.reveal.at-end.open {
  margin-top: 0;
}
.reveal > div {
  min-height: 0;
  overflow: hidden;
  margin: -0.25rem; /* room for focus rings inside the clip */
  padding: 0.25rem;
}

.swap-enter-active,
.swap-leave-active {
  transition:
    opacity 0.18s ease,
    transform 0.18s ease;
}
.swap-enter-from {
  opacity: 0;
  transform: translateY(4px);
}
.swap-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}
</style>
