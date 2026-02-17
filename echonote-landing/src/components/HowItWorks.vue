<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { projectConfig } from '../config/project'

const { t } = useI18n()

const steps = computed(() =>
  (projectConfig.howItWorks || []).map((step) => ({
    ...step,
    stepLabel: String(step.step).padStart(2, '0'),
  })),
)
</script>

<template>
  <section id="how-it-works" aria-labelledby="how-it-works-title" class="section-shell relative overflow-hidden bg-slate-50">
    <div class="absolute inset-0 pointer-events-none">
      <div class="absolute top-0 left-0 w-full h-px bg-gradient-to-r from-transparent via-slate-200 to-transparent"></div>
      <div class="absolute bottom-0 right-0 h-1/2 w-1/2 rounded-full bg-gradient-to-tl from-blue-50/50 to-transparent blur-3xl"></div>
    </div>

    <div class="site-container relative">
      <div class="section-head mb-14">
        <h2 id="how-it-works-title" class="mb-4 text-3xl font-bold text-slate-900 sm:text-4xl">
          {{ t('howItWorks.title') }}
        </h2>
        <p class="text-lg text-slate-600">
          {{ t('howItWorks.subtitle') }}
        </p>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-3 gap-8 relative">
        <div class="absolute left-0 top-12 hidden h-0.5 w-full -z-10 translate-y-4 bg-gradient-to-r from-blue-100 via-indigo-100 to-sky-100 md:block"></div>

        <article
          v-for="(step, index) in steps"
          :key="step.step"
          class="relative group"
        >
          <div class="relative z-10 h-full rounded-2xl border border-slate-100 bg-white p-6 shadow-lg transition-all duration-300 group-hover:-translate-y-1 group-hover:shadow-xl">
            <div class="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-blue-500 to-indigo-600 text-xl font-bold text-white shadow-lg transition-transform duration-300 group-hover:scale-110">
              {{ step.stepLabel }}
            </div>

            <h3 class="text-xl font-bold text-slate-900 text-center mb-3">
              {{ t(step.title) }}
            </h3>
            <p class="text-slate-600 text-center leading-relaxed">
              {{ t(step.description) }}
            </p>
          </div>

          <div v-if="index < steps.length - 1" class="md:hidden flex justify-center py-4">
            <svg class="w-6 h-6 text-slate-300 animate-bounce" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 14l-7 7m0 0l-7-7m7 7V3" />
            </svg>
          </div>
        </article>
      </div>
    </div>
  </section>
</template>
