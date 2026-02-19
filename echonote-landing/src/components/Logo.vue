<script setup lang="ts">
import { projectConfig } from '../config/project'

interface Props {
  className?: string
  loading?: 'eager' | 'lazy'
}

withDefaults(defineProps<Props>(), {
  className: '',
  loading: 'lazy',
})
</script>

<template>
  <img
    src="/Logo.png"
    :alt="`${projectConfig.name} logo`"
    :class="['rounded-lg border border-slate-200/70', className]"
    :loading="loading"
  />
</template>
