<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import type { Feature } from '../types'

const { t } = useI18n()

interface Props {
  features: Feature[]
  title?: string
  subtitle?: string
}

withDefaults(defineProps<Props>(), {
  title: 'features.title',
  subtitle: 'features.subtitle'
})

// Helper to determine if a feature should span columns (Bento Grid effect)
const getSpanClass = (index: number) => {
  // First item spans 2 cols, others 1
  if (index === 0) return 'md:col-span-2 md:row-span-2'
  if (index === 3) return 'md:col-span-1' // Keep visual weight balanced
  return 'md:col-span-1'
}

const getBgClass = (index: number) => {
  if (index === 0) return 'bg-gradient-to-br from-blue-50 to-indigo-50 border-blue-100'
  return 'bg-white border-slate-100'
}
</script>

<template>
  <section id="features" aria-labelledby="features-title" class="section-shell bg-white">
    <div class="site-container">
      <div class="section-head mb-14">
        <h2 id="features-title" class="mb-4 text-3xl font-bold text-slate-900 sm:text-4xl">
          {{ t(title) }}
        </h2>
        <p class="text-lg text-slate-600">
          {{ t(subtitle) }}
        </p>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-3 gap-6 auto-rows-[minmax(200px,auto)]">
        <article
          v-for="(feature, index) in features"
          :key="feature.id"
          class="group relative rounded-2xl p-8 border transition-all duration-300 hover:shadow-xl hover:-translate-y-1 overflow-hidden"
          :class="[getSpanClass(index), getBgClass(index)]"
        >
          <div class="absolute inset-0 bg-gradient-to-br from-transparent to-blue-50/50 opacity-0 group-hover:opacity-100 transition-opacity duration-500"></div>

          <div class="relative z-10 flex flex-col h-full">
            <div class="w-12 h-12 rounded-xl bg-white shadow-sm border border-slate-100 flex items-center justify-center text-3xl mb-6 group-hover:scale-110 transition-transform duration-300">
              {{ feature.icon }}
            </div>

            <h3 class="text-xl font-bold text-slate-900 mb-2">
              {{ t(feature.title) }}
            </h3>
            
            <p class="text-slate-600 leading-relaxed">
              {{ t(feature.description) }}
            </p>

            <div v-if="index === 0" class="mt-auto pt-8">
               <div class="h-1 w-20 bg-gradient-to-r from-blue-500 to-indigo-500 rounded-full"></div>
            </div>
          </div>
        </article>
      </div>
    </div>
  </section>
</template>
