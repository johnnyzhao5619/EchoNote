<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { Feature } from '../types'

const { t } = useI18n()

interface Props {
  features: Feature[]
  columns?: number
  title?: string
  subtitle?: string
}

const props = withDefaults(defineProps<Props>(), {
  columns: 3,
  title: 'features.title',
  subtitle: 'features.subtitle'
})

// Compute grid classes based on columns
const gridClasses = computed(() => {
  const colsMap = {
    1: 'grid-cols-1',
    2: 'grid-cols-1 md:grid-cols-2',
    3: 'grid-cols-1 md:grid-cols-2 lg:grid-cols-3',
    4: 'grid-cols-1 md:grid-cols-2 lg:grid-cols-4',
    6: 'grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6'
  }
  return colsMap[props.columns as keyof typeof colsMap] || 'grid-cols-1 md:grid-cols-2 lg:grid-cols-3'
})
</script>

<template>
  <section class="py-12 sm:py-16 md:py-20 bg-white">
    <div class="max-w-7xl mx-auto px-3 sm:px-6 lg:px-8">
      <!-- Section header -->
      <div class="text-center mb-10 sm:mb-12 md:mb-16">
        <h2 class="text-2xl sm:text-3xl md:text-4xl font-bold text-gray-900 mb-3 sm:mb-4 px-2">
          {{ t(title) }}
        </h2>
        <p v-if="subtitle" class="text-lg sm:text-xl text-gray-600 max-w-3xl mx-auto px-4">
          {{ t(subtitle) }}
        </p>
      </div>
      
      <!-- Features grid -->
      <div :class="`grid ${gridClasses} gap-4 sm:gap-6 md:gap-8`">
        <div 
          v-for="(feature, index) in features" 
          :key="feature.id"
          class="group relative text-center p-4 sm:p-6 md:p-8 rounded-lg sm:rounded-xl border border-gray-200 hover:border-blue-300 hover:shadow-xl transition-all duration-300 transform active:scale-95 sm:hover:-translate-y-2 bg-white touch-manipulation cursor-pointer overflow-hidden"
          :class="{
            'animate-fade-in-up': true,
            'animation-delay-100': index % 3 === 1,
            'animation-delay-200': index % 3 === 2
          }"
        >
          <!-- Feature icon -->
          <div class="relative mb-4 sm:mb-6">
            <div class="w-12 h-12 sm:w-14 sm:h-14 md:w-16 md:h-16 mx-auto bg-gradient-to-br from-blue-50 to-indigo-100 rounded-xl sm:rounded-2xl flex items-center justify-center group-hover:from-blue-100 group-hover:to-indigo-200 transition-all duration-300 group-hover:rotate-6 group-hover:scale-110">
              <span class="text-2xl sm:text-3xl transition-transform duration-300 group-hover:scale-110">{{ feature.icon }}</span>
            </div>
            <!-- Decorative ring -->
            <div class="absolute inset-0 w-12 h-12 sm:w-14 sm:h-14 md:w-16 md:h-16 mx-auto rounded-xl sm:rounded-2xl border-2 border-blue-200 opacity-0 group-hover:opacity-100 group-hover:scale-125 transition-all duration-300"></div>
            <!-- Pulse effect -->
            <div class="absolute inset-0 w-12 h-12 sm:w-14 sm:h-14 md:w-16 md:h-16 mx-auto rounded-xl sm:rounded-2xl bg-blue-400 opacity-0 group-hover:opacity-20 group-hover:scale-150 transition-all duration-500"></div>
          </div>

          <!-- Feature title -->
          <h3 class="text-lg sm:text-xl font-semibold text-gray-900 mb-3 sm:mb-4 group-hover:text-blue-600 transition-all duration-300 px-2 transform group-hover:scale-105">
            {{ feature.title }}
          </h3>

          <!-- Feature description -->
          <p class="text-sm sm:text-base text-gray-600 leading-relaxed px-2 transition-all duration-300 group-hover:text-gray-700">
            {{ feature.description }}
          </p>

          <!-- Hover effect background -->
          <div class="absolute inset-0 bg-gradient-to-br from-blue-50/50 to-indigo-50/50 rounded-lg sm:rounded-xl opacity-0 group-hover:opacity-100 transition-opacity duration-300 -z-10"></div>
          
          <!-- Shimmer effect -->
          <div class="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent -translate-x-full group-hover:translate-x-full transition-transform duration-1000 -z-10"></div>
        </div>
      </div>

      <!-- Call to action -->
      <div class="text-center mt-10 sm:mt-12 md:mt-16 px-4">
        <p class="text-sm sm:text-base text-gray-600 mb-4 sm:mb-6">{{ t('features.callToAction') }}</p>
        <a 
          href="#github-stats" 
          class="inline-flex items-center px-4 sm:px-6 py-3 bg-gradient-to-r from-blue-600 to-indigo-600 text-white font-semibold rounded-lg hover:from-blue-700 hover:to-indigo-700 transition-all duration-200 transform active:scale-95 sm:hover:scale-105 shadow-lg hover:shadow-xl touch-manipulation"
        >
          {{ t('features.exploreMore') }}
          <svg class="w-4 h-4 sm:w-5 sm:h-5 ml-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 14l-7 7m0 0l-7-7m7 7V3" />
          </svg>
        </a>
      </div>
    </div>
  </section>
</template>

