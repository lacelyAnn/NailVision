<script setup lang="ts">
import { ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import { Button } from '@/components/ui/button'
import { supabase, type Company } from '@/lib/supabase'
import type { SavedDesign } from '@/stores/designs'

const props = defineProps<{ design: SavedDesign | null }>()
const emit = defineEmits<{ close: [] }>()
const dlg = ref<HTMLDialogElement>()
const companies = ref<Company[]>([])
const companyId = ref('')
const note = ref('')
const busy = ref(false)
const error = ref('')
const done = ref(false)

watch(
  () => props.design,
  async (d) => {
    if (!d) return dlg.value?.close()
    error.value = note.value = ''
    done.value = false
    dlg.value?.showModal()
    if (!companies.value.length)
      companies.value = (await supabase.from('companies').select('*').order('name')).data ?? []
  },
  { flush: 'post' },
)

async function book() {
  const d = props.design
  if (!d) return
  busy.value = true
  error.value = ''
  const { error: e } = await supabase.from('bookings').insert({
    company_id: companyId.value,
    style: d.style,
    kind: d.kind,
    palette_hex: d.palette_hex,
    zoom: d.zoom,
    client_rating: d.rating,
    client_note: note.value,
  })
  busy.value = false
  if (e) error.value = e.message
  else done.value = true
}
</script>

<template>
  <dialog
    ref="dlg"
    class="bg-card m-auto w-[min(26rem,calc(100%-2rem))] rounded-2xl border p-5 backdrop:bg-black/60"
    aria-labelledby="book-title"
    @close="emit('close')"
  >
    <h2 id="book-title" class="font-display text-lg font-bold">Book this design at a salon</h2>
    <div v-if="design" class="mt-3 flex items-center gap-3">
      <img
        :src="`data:image/jpeg;base64,${design.zoom}`"
        alt=""
        class="bg-muted size-16 rounded-lg object-contain"
      />
      <p class="text-sm font-semibold capitalize">{{ design.style }}</p>
    </div>

    <div v-if="done" class="mt-4 flex flex-col gap-3 text-sm" role="status">
      <p>Sent. A nail technician at the salon will review your design.</p>
      <div class="flex gap-2">
        <Button as-child size="sm"
          ><RouterLink to="/client/bookings">My bookings</RouterLink></Button
        >
        <Button size="sm" variant="outline" @click="emit('close')">Close</Button>
      </div>
    </div>
    <form v-else class="mt-4 flex flex-col gap-3" @submit.prevent="book">
      <fieldset class="flex flex-col gap-2">
        <legend class="mb-1 text-sm font-medium">Choose a company</legend>
        <label
          v-for="c in companies"
          :key="c.id"
          class="has-[:checked]:border-primary has-[:checked]:bg-accent flex cursor-pointer items-center gap-3 rounded-lg border p-3 text-sm has-[:focus-visible]:ring-[3px]"
        >
          <input v-model="companyId" type="radio" :value="c.id" required class="accent-primary" />
          <span>
            <span class="font-semibold">{{ c.name }}</span>
            <span v-if="c.address" class="text-muted-foreground block text-xs">{{
              c.address
            }}</span>
          </span>
        </label>
      </fieldset>
      <label class="text-sm font-medium"
        >Note for the technician (optional)
        <textarea
          v-model="note"
          rows="2"
          maxlength="500"
          class="bg-background focus-visible:ring-ring/50 mt-1 w-full rounded-lg border px-3 py-2 text-sm outline-none focus-visible:ring-[3px]"
        />
      </label>
      <p v-if="error" class="text-destructive text-sm" role="alert">{{ error }}</p>
      <div class="flex justify-end gap-2">
        <Button type="button" variant="outline" @click="emit('close')">Cancel</Button>
        <Button type="submit" :disabled="busy || !companyId">Send booking</Button>
      </div>
    </form>
  </dialog>
</template>
