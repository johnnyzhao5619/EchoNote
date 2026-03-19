<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import type { Feature } from '../types'
import SectionHeading from './ui/SectionHeading.vue'

const { t } = useI18n()

interface Props {
  features: Feature[]
}

defineProps<Props>()
</script>

<template>
  <section
    id="features"
    aria-labelledby="features-title"
    class="py-16 sm:py-24 bg-white dark:bg-gray-900"
  >
    <div class="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
      <SectionHeading :title="t('features.title')" :subtitle="t('features.subtitle')" />

      <div class="mx-auto mt-16 max-w-2xl sm:mt-20 lg:mt-24 lg:max-w-none">
        <dl class="grid max-w-xl grid-cols-1 gap-x-8 gap-y-16 lg:max-w-none lg:grid-cols-3">
          <div
            v-for="feature in features"
            :key="feature.id"
            class="flex flex-col rounded-2xl bg-gray-50 dark:bg-gray-800/50 p-8 ring-1 ring-gray-900/5 dark:ring-white/10 hover:shadow-lg transition-shadow duration-300"
          >
            <dt
              class="flex flex-col items-start gap-4 text-xl font-semibold leading-7 text-gray-900 dark:text-white"
            >
              <div
                class="flex h-12 w-12 items-center justify-center rounded-lg bg-blue-600/10 dark:bg-blue-900/40 text-2xl"
              >
                {{ feature.icon }}
              </div>
              {{ t(feature.title) }}
            </dt>
            <dd
              class="mt-4 flex flex-auto flex-col text-base leading-7 text-gray-600 dark:text-gray-300"
            >
              <p class="flex-auto">{{ t(feature.description) }}</p>
            </dd>
          </div>
        </dl>
      </div>
    </div>
  </section>
</template>
