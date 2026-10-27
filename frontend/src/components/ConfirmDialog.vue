<script setup lang="ts">
import { ref, watch } from 'vue'
import { Trash2, Loader } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'

const props = defineProps<{
  open: boolean
  title: string
  message: string
  confirmLabel: string
  dismissLabel?: string
  image?: string // base64 jpeg of the item being deleted
  busy?: boolean
}>()
const emit = defineEmits<{ confirm: []; close: [] }>()
const dlg = ref<HTMLDialogElement>()

// showModal focuses the first button: Cancel, the safe choice
watch(
  () => props.open,
  (o) => (o ? dlg.value?.showModal() : dlg.value?.close()),
  { flush: 'post' },
)
</script>

<template>
  <dialog
    ref="dlg"
    class="bg-card text-foreground animate-in fade-in-0 zoom-in-95 m-auto w-[min(24rem,calc(100%-2rem))] rounded-2xl border p-0 shadow-xl duration-150 backdrop:bg-[#0b1f55]/40 backdrop:backdrop-blur-sm motion-reduce:animate-none"
    aria-labelledby="confirm-title"
    aria-describedby="confirm-message"
    @close="emit('close')"
    @cancel="busy && $event.preventDefault()"
    @click.self="!busy && dlg?.close()"
  >
    <div class="flex flex-col gap-4 p-6">
      <div class="flex items-start gap-4">
        <span
          class="bg-destructive/10 text-destructive grid size-11 shrink-0 place-items-center rounded-full"
        >
          <Trash2 class="size-5" />
        </span>
        <div class="min-w-0">
          <h2 id="confirm-title" class="font-display text-lg leading-snug font-bold">
            {{ title }}
          </h2>
          <p id="confirm-message" class="text-muted-foreground mt-1 text-sm leading-relaxed">
            {{ message }}
          </p>
        </div>
      </div>
      <img
        v-if="image"
        :src="`data:image/jpeg;base64,${image}`"
        alt=""
        class="bg-muted h-28 w-full rounded-xl border object-contain"
      />
    </div>
    <div class="bg-muted/60 flex flex-col-reverse gap-2 border-t px-6 py-4 sm:flex-row sm:justify-end">
      <Button variant="outline" :disabled="busy" @click="dlg?.close()">{{
        dismissLabel ?? 'Cancel'
      }}</Button>
      <Button
        class="bg-destructive hover:bg-destructive/90 focus-visible:ring-destructive/40 text-white"
        :disabled="busy"
        @click="emit('confirm')"
      >
        <Loader v-if="busy" class="animate-spin" />
        {{ confirmLabel }}
      </Button>
    </div>
  </dialog>
</template>
