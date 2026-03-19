<script setup lang="ts">
defineProps<{
  title: string
  subtitle?: string
  align?: 'left' | 'center'
}>()
</script>

<template>
  <div :class="[align === 'left' ? 'text-left' : 'text-center max-w-3xl mx-auto', 'mb-12']">
    <h2 class="text-3xl font-bold tracking-tight text-gray-900 dark:text-white sm:text-4xl">
      {{ title }}
    </h2>
    <p v-if="subtitle" class="mt-4 text-lg text-gray-600 dark:text-gray-300">
      {{ subtitle }}
    </p>
  </div>
</template>
