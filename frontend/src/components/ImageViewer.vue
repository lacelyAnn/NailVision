<script setup lang="ts">
import { ref, watch } from 'vue'
import { X } from 'lucide-vue-next'

const props = defineProps<{ src: string | null; alt: string }>()
const emit = defineEmits<{ close: [] }>()
const dlg = ref<HTMLDialogElement>()

// native <dialog>: full-screen overlay, Esc to close, focus trapped for free
watch(
  () => props.src,
  (v) => (v ? dlg.value?.showModal() : dlg.value?.close()),
  { flush: 'post' },
)
</script>

<template>
  <dialog
    ref="dlg"
    class="m-0 size-full max-h-none max-w-none bg-transparent p-0 backdrop:bg-black/90"
    @close="emit('close')"
  >
    <div class="flex size-full items-center justify-center p-4 sm:p-8" @click.self="emit('close')">
      <img
        v-if="src"
        :src="src"
        :alt="alt"
        class="max-h-full max-w-full rounded-lg object-contain"
      />
      <button
        type="button"
        class="focus-visible:ring-ring absolute top-4 right-4 grid size-10 cursor-pointer place-items-center rounded-full bg-white/15 text-white outline-none hover:bg-white/25 focus-visible:ring-[3px]"
        aria-label="Close full screen view"
        @click="emit('close')"
      >
        <X class="size-5" />
      </button>
    </div>
  </dialog>
</template>
