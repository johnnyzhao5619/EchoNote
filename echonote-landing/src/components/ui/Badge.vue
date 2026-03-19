<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    variant?: 'primary' | 'success' | 'warning' | 'danger' | 'neutral'
  }>(),
  {
    variant: 'primary',
  },
)

const variantClasses = computed(() => {
  switch (props.variant) {
    case 'success':
      return 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200 ring-green-600/20'
    case 'warning':
      return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200 ring-yellow-600/20'
    case 'danger':
      return 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200 ring-red-600/20'
    case 'neutral':
      return 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400 ring-gray-500/10'
    case 'primary':
    default:
      return 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300 ring-blue-700/10'
  }
})
</script>

<template>
  <span
    class="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset"
    :class="variantClasses"
  >
    <slot></slot>
  </span>
</template>
