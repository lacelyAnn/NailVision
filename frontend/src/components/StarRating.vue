<script setup lang="ts">
import { Star } from 'lucide-vue-next'

defineProps<{ modelValue: number; label?: string; readonly?: boolean }>()
defineEmits<{ 'update:modelValue': [n: number] }>()
</script>

<template>
  <div class="flex items-center gap-0.5" role="radiogroup" :aria-label="label ?? 'Rating'">
    <button
      v-for="n in 5"
      :key="n"
      type="button"
      role="radio"
      :aria-checked="modelValue === n"
      :aria-label="`${n} ${n === 1 ? 'star' : 'stars'}`"
      :disabled="readonly"
      class="focus-visible:ring-ring/50 rounded p-0.5 outline-none focus-visible:ring-[3px] enabled:cursor-pointer"
      @click="$emit('update:modelValue', modelValue === n ? 0 : n)"
    >
      <Star
        class="size-4 transition-colors"
        :class="n <= modelValue ? 'fill-amber-500 text-amber-600' : 'text-muted-foreground'"
      />
    </button>
  </div>
</template>
