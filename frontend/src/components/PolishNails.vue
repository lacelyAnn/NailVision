<script setup lang="ts">
// one hand, five polishes: the five designs the studio paints for you
withDefaults(defineProps<{ scale?: number }>(), { scale: 1 })

const nails = [
  { color: '#7a1f3d', h: 3, lift: 0.4, w: 2.5 },
  { color: '#b8305c', h: 3.8, lift: 1.4, w: 2.5 },
  { color: '#f27b9d', h: 4.2, lift: 1.9, w: 2.5 },
  { color: '#e9b8a7', h: 3.9, lift: 1.3, w: 2.5 },
  { color: '#0b1f55', h: 3.5, lift: 0, w: 3 },
]
</script>

<template>
  <div
    class="flex items-end"
    :style="{ gap: `${0.625 * scale}rem`, height: `${7 * scale}rem` }"
    aria-hidden="true"
  >
    <span
      v-for="(n, i) in nails"
      :key="i"
      class="nail"
      :style="{
        '--c': n.color,
        '--i': i,
        height: `${n.h * scale}rem`,
        width: `${n.w * scale}rem`,
        marginBottom: `${n.lift * scale}rem`,
      }"
    />
  </div>
</template>

<style scoped>
/* polish painted on from cuticle to tip, one nail after another */
.nail {
  position: relative;
  flex: none;
  border-radius: 48% 48% 42% 42% / 62% 62% 30% 30%;
  background: var(--c);
  box-shadow: inset 0 -5px 0 rgb(0 0 0 / 0.14);
  animation: paint 0.7s cubic-bezier(0.22, 1, 0.36, 1) both;
  animation-delay: calc(var(--i) * 90ms + 150ms);
}
.nail::after {
  /* gloss */
  content: '';
  position: absolute;
  top: 14%;
  left: 22%;
  width: 18%;
  height: 42%;
  border-radius: 999px;
  background: rgb(255 255 255 / 0.45);
}
@keyframes paint {
  from {
    clip-path: inset(100% 0 0 0);
  }
  to {
    clip-path: inset(0);
  }
}
@media (prefers-reduced-motion: reduce) {
  .nail {
    animation: none;
  }
}
</style>
