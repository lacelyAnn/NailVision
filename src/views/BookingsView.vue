<script setup lang="ts">
import { ref, computed, onActivated } from 'vue'
import { RouterLink } from 'vue-router'
import { Trash2 } from 'lucide-vue-next'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import StarRating from '@/components/StarRating.vue'
import ImageViewer from '@/components/ImageViewer.vue'
import { useAuth } from '@/stores/auth'
import { supabase, type Booking } from '@/lib/supabase'

const auth = useAuth()
const tech = computed(() => auth.profile?.role === 'technician')
const items = ref<Booking[]>([])
const loading = ref(true)
const error = ref('')
const view = ref<string | null>(null)
const saving = ref('')

const statuses = {
  pending: 'Waiting for review',
  accepted: 'Accepted',
  changes: 'Needs changes',
  done: 'Done',
} as const

// RLS does the filtering: a client gets their own bookings, a technician their company's
async function load() {
  error.value = ''
  const { data, error: e } = await supabase
    .from('bookings')
    .select('*, companies(name), profiles!bookings_client_id_fkey(full_name)')
    .order('created_at', { ascending: false })
  if (e) error.value = e.message
  items.value = data ?? []
  loading.value = false
}
onActivated(load) // KeepAlive: refresh each time the page is opened

async function review(b: Booking) {
  saving.value = b.id
  const { status, tech_rating, tech_note } = b
  const { error: e } = await supabase
    .from('bookings')
    .update({ status, tech_rating, tech_note, technician_id: auth.profile!.id })
    .eq('id', b.id)
  saving.value = ''
  if (e) error.value = e.message
}

async function cancel(b: Booking) {
  if (!confirm('Cancel this booking?')) return
  const { error: e } = await supabase.from('bookings').delete().eq('id', b.id)
  if (e) error.value = e.message
  else items.value = items.value.filter((x) => x.id !== b.id)
}

const when = (t: string) =>
  new Date(t).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
</script>

<template>
  <div>
    <div class="bg-card/90 mb-6 rounded-2xl p-4 backdrop-blur">
      <h1 class="font-display text-3xl font-extrabold tracking-tight">
        {{ tech ? 'Design reviews' : 'My bookings' }}
      </h1>
      <p class="text-muted-foreground mt-1.5 text-sm">
        {{
          tech
            ? 'Clients who chose your salon. Check each AI design and tell them if it works.'
            : 'Designs you sent to a salon, and what the nail technician thinks.'
        }}
      </p>
    </div>

    <p v-if="error" class="text-destructive bg-card mb-4 rounded-lg p-3 text-sm" role="alert">
      {{ error }}
    </p>
    <p v-if="loading" class="text-muted-foreground bg-card/90 w-fit rounded-lg p-3 text-sm">
      Loading…
    </p>
    <div
      v-else-if="!items.length"
      class="text-muted-foreground bg-card/90 rounded-2xl border-2 border-dashed p-10 text-center text-sm"
    >
      <p>{{ tech ? 'No bookings for your salon yet.' : 'No bookings yet.' }}</p>
      <RouterLink
        v-if="!tech"
        to="/client/history"
        class="text-primary mt-2 inline-block font-medium underline"
      >
        Pick a design to book
      </RouterLink>
    </div>

    <div class="flex flex-col gap-4">
      <Card v-for="b in items" :key="b.id" class="flex flex-col gap-4 p-4 sm:flex-row">
        <button
          type="button"
          class="focus-visible:ring-ring/50 shrink-0 cursor-zoom-in self-start rounded-lg outline-none focus-visible:ring-[3px]"
          :aria-label="`View ${b.style} design full screen`"
          @click="view = `data:image/jpeg;base64,${b.zoom}`"
        >
          <img
            :src="`data:image/jpeg;base64,${b.zoom}`"
            :alt="`${b.style} design`"
            class="bg-muted size-36 rounded-lg object-contain"
          />
        </button>

        <div class="flex min-w-0 flex-1 flex-col gap-2 text-sm">
          <div class="flex flex-wrap items-center gap-2">
            <p class="font-display font-bold capitalize">{{ b.style }}</p>
            <Badge variant="outline">{{
              b.kind === 'palette' ? 'Client polishes' : 'AI suggested'
            }}</Badge>
            <Badge :variant="b.status === 'pending' ? 'outline' : 'default'">
              {{ statuses[b.status] }}
            </Badge>
          </div>
          <p class="text-muted-foreground text-xs">
            {{ when(b.created_at) }} ·
            {{ tech ? b.profiles?.full_name || 'Client' : b.companies?.name }}
          </p>
          <div class="flex items-center gap-1">
            <i
              v-for="c in b.palette_hex"
              :key="c"
              class="ring-foreground/30 size-4 rounded-full ring-1"
              :style="{ background: c }"
            />
          </div>
          <div class="flex items-center gap-2 text-xs">
            Client rating
            <StarRating :model-value="b.client_rating" readonly label="Client rating" />
          </div>
          <p v-if="b.client_note" class="bg-muted rounded-lg p-2 text-xs">“{{ b.client_note }}”</p>

          <form
            v-if="tech"
            class="mt-1 flex flex-col gap-2 border-t pt-3"
            @submit.prevent="review(b)"
          >
            <div class="flex flex-wrap items-center gap-3 text-xs">
              <label class="flex items-center gap-2"
                >Status
                <select v-model="b.status" class="bg-background rounded-md border px-2 py-1">
                  <option v-for="(label, s) in statuses" :key="s" :value="s">{{ label }}</option>
                </select>
              </label>
              <span class="flex items-center gap-2">
                Worth it?
                <StarRating v-model="b.tech_rating" label="Technician rating" />
              </span>
            </div>
            <textarea
              v-model="b.tech_note"
              rows="2"
              maxlength="1000"
              placeholder="Advice for the client: is the design doable, how long, what to change…"
              aria-label="Review note"
              class="bg-background focus-visible:ring-ring/50 w-full rounded-lg border px-3 py-2 text-sm outline-none focus-visible:ring-[3px]"
            />
            <Button type="submit" size="sm" class="self-start" :disabled="saving === b.id">
              {{ saving === b.id ? 'Saving…' : 'Save review' }}
            </Button>
          </form>

          <div v-else class="mt-1 flex flex-col gap-2 border-t pt-3">
            <template v-if="b.status !== 'pending'">
              <div class="flex items-center gap-2 text-xs">
                Technician says
                <StarRating :model-value="b.tech_rating" readonly label="Technician rating" />
              </div>
              <p v-if="b.tech_note" class="bg-accent rounded-lg p-2 text-xs">{{ b.tech_note }}</p>
            </template>
            <Button v-else variant="outline" size="sm" class="self-start" @click="cancel(b)"
              ><Trash2 /> Cancel booking</Button
            >
          </div>
        </div>
      </Card>
    </div>

    <ImageViewer :src="view" alt="Design in full screen" @close="view = null" />
  </div>
</template>
