<script setup lang="ts">
import type { HTMLAttributes } from 'vue'
import { SliderRange, SliderRoot, SliderThumb, SliderTrack, useForwardPropsEmits } from 'reka-ui'
import type { SliderRootEmits, SliderRootProps } from 'reka-ui'
import { cn } from '@/lib/utils'

const props = defineProps<SliderRootProps & { class?: HTMLAttributes['class'] }>()
const emits = defineEmits<SliderRootEmits>()
const forwarded = useForwardPropsEmits(
  (({ class: _c, ...rest }) => rest)(props) as SliderRootProps,
  emits,
)
</script>

<template>
  <SliderRoot
    v-bind="forwarded"
    :class="cn('relative flex w-full touch-none items-center select-none h-5', props.class)"
  >
    <SliderTrack class="relative h-1.5 w-full grow overflow-hidden rounded-full bg-muted">
      <SliderRange class="absolute h-full bg-primary" />
    </SliderTrack>
    <SliderThumb
      v-for="(_, i) in modelValue ?? defaultValue"
      :key="i"
      class="block size-5 rounded-full border-2 border-primary bg-card shadow outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
    />
  </SliderRoot>
</template>
