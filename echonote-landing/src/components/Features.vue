<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import type { Feature } from '../types'

const { t } = useI18n()

interface Props {
  features: Feature[]
}

defineProps<Props>()
</script>

<template>
  <section id="features" aria-labelledby="features-title" class="section-shell bg-white">
    <div class="site-container">
      <div class="section-head mb-14">
        <h2 id="features-title" class="mb-4 text-3xl font-bold text-slate-900 sm:text-4xl">
          {{ t('features.title') }}
        </h2>
        <p class="text-lg text-slate-600">
          {{ t('features.subtitle') }}
        </p>
      </div>

      <div class="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
        <article
          v-for="feature in features"
          :key="feature.id"
          class="landing-card h-full p-6 sm:p-7"
        >
          <div class="flex h-full flex-col">
            <div
              class="mb-5 inline-flex h-11 w-11 items-center justify-center rounded-xl border border-slate-200 bg-slate-50 text-2xl"
            >
              {{ feature.icon }}
            </div>

            <h3 class="mb-2 text-xl font-semibold text-slate-900">
              {{ t(feature.title) }}
            </h3>

            <p class="leading-relaxed text-slate-600">
              {{ t(feature.description) }}
            </p>
          </div>
        </article>
      </div>
    </div>
  </section>
</template>
