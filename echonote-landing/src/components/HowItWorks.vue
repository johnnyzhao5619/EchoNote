<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import type { HowItWorksStep } from '../types'

const { t } = useI18n()

interface Props {
  steps: HowItWorksStep[]
}

defineProps<Props>()
</script>

<template>
  <section id="how-it-works" aria-labelledby="how-it-works-title" class="section-shell bg-slate-50/70">
    <div class="site-container">
      <div class="section-head mb-14">
        <h2 id="how-it-works-title" class="mb-4 text-3xl font-semibold text-slate-900 sm:text-4xl">
          {{ t('howItWorks.title') }}
        </h2>
        <p class="text-lg text-slate-600">
          {{ t('howItWorks.subtitle') }}
        </p>
      </div>

      <div class="grid grid-cols-1 gap-5 md:grid-cols-3">
        <article
          v-for="step in steps"
          :key="step.step"
          class="landing-card relative h-full overflow-hidden p-6 sm:p-7"
        >
          <span
            class="mb-4 inline-flex rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-bold tracking-wider text-slate-400"
          >
            {{ String(step.step).padStart(2, '0') }}
          </span>
          <h3 class="mb-3 text-xl font-semibold text-slate-900">
            {{ t(step.title) }}
          </h3>
          <p class="leading-relaxed text-slate-600">
            {{ t(step.description) }}
          </p>
          <div
            class="absolute bottom-0 left-0 h-1 w-full bg-gradient-to-r from-blue-500/70 via-cyan-500/60 to-indigo-500/70"
          ></div>
        </article>
      </div>
    </div>
  </section>
</template>
