<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { projectConfig } from '../config/project'
import { useResponsiveImage } from '../composables/useLogo'
import type { ActionButton } from '../types'

const { t } = useI18n()

// Banner image handling
const { 
  imageSrc: bannerSrc, 
  isLoading: bannerLoading, 
  hasError: bannerError, 
  imageAlt: bannerAlt,
  handleImageError: handleBannerError,
  handleImageLoad: handleBannerLoad
} = useResponsiveImage('/Banner.png', 'EchoNote application interface preview')

interface Props {
  title?: string
  description?: string
  primaryAction?: ActionButton
  secondaryAction?: ActionButton
  backgroundImage?: string
}

withDefaults(defineProps<Props>(), {
  title: () => projectConfig.name,
  description: () => projectConfig.description,
  primaryAction: () => ({
    text: 'hero.viewOnGitHub',
    url: projectConfig.githubUrl,
    type: 'primary' as const,
    external: true
  })
})

// Button style classes - optimized for mobile
const buttonClasses = {
  base: 'inline-flex items-center justify-center px-4 sm:px-6 py-3 sm:py-3 font-semibold rounded-lg transition-all duration-200 transform active:scale-95 sm:hover:scale-105',
  primary: 'bg-blue-600 text-white hover:bg-blue-700 active:bg-blue-800 shadow-lg hover:shadow-xl',
  secondary: 'bg-white text-blue-600 border-2 border-blue-600 hover:bg-blue-50 active:bg-blue-100 shadow-md hover:shadow-lg'
}

const getButtonClasses = (type: 'primary' | 'secondary') => 
  `${buttonClasses.base} ${buttonClasses[type]}`
</script>

<template>
  <section 
    class="relative bg-gradient-to-br from-blue-50 via-indigo-50 to-purple-50 py-12 sm:py-16 md:py-20 lg:py-32 overflow-hidden"
    :style="backgroundImage ? `background-image: url(${backgroundImage})` : ''"
  >
    <!-- Background decoration -->
    <div class="absolute inset-0 bg-gradient-to-br from-blue-600/5 to-purple-600/5"></div>
    
    <!-- Animated background elements for desktop -->
    <div class="absolute inset-0 overflow-hidden pointer-events-none">
      <div class="absolute -top-40 -right-40 w-80 h-80 bg-gradient-to-br from-blue-400/10 to-purple-400/10 rounded-full blur-3xl animate-pulse"></div>
      <div class="absolute -bottom-40 -left-40 w-80 h-80 bg-gradient-to-tr from-indigo-400/10 to-pink-400/10 rounded-full blur-3xl animate-pulse animation-delay-1000"></div>
    </div>

    <div class="relative max-w-7xl mx-auto px-3 sm:px-6 lg:px-8 text-center">
      <!-- Main title -->
      <h1 class="text-3xl sm:text-4xl md:text-6xl lg:text-7xl font-bold text-gray-900 mb-4 sm:mb-6 leading-tight animate-fade-in-up">
        <span class="bg-gradient-to-r from-blue-600 via-indigo-600 to-purple-600 bg-clip-text text-transparent bg-size-200 animate-gradient-x">
          {{ title }}
        </span>
      </h1>

      <!-- Description -->
      <p class="text-lg sm:text-xl md:text-2xl lg:text-3xl text-gray-600 mb-8 sm:mb-10 md:mb-12 max-w-4xl mx-auto leading-relaxed px-2 animate-fade-in-up animation-delay-300">
        {{ description }}
      </p>

      <!-- Action buttons -->
      <div class="flex flex-col sm:flex-row gap-3 sm:gap-4 justify-center items-center px-4 animate-fade-in-up animation-delay-600">
        <!-- Primary action button -->
        <a 
          v-if="primaryAction"
          :href="primaryAction.url"
          :target="primaryAction.external ? '_blank' : '_self'"
          :rel="primaryAction.external ? 'noopener noreferrer' : ''"
          :class="`${getButtonClasses(primaryAction.type)} group w-full sm:w-auto min-w-[200px] text-center touch-manipulation relative overflow-hidden`"
        >
          <div class="absolute inset-0 bg-gradient-to-r from-blue-700 to-purple-700 opacity-0 group-hover:opacity-100 transition-opacity duration-300"></div>
          <div class="relative flex items-center justify-center">
            <svg v-if="primaryAction.external" class="w-4 h-4 sm:w-5 sm:h-5 mr-2 transition-transform duration-200 group-hover:rotate-12" fill="currentColor" viewBox="0 0 20 20">
              <path fill-rule="evenodd" d="M10.868 2.884c-.321-.772-1.415-.772-1.736 0l-1.83 4.401-4.753.381c-.833.067-1.171 1.107-.536 1.651l3.62 3.102-1.106 4.637c-.194.813.691 1.456 1.405 1.02L10 15.591l4.069 2.485c.713.436 1.598-.207 1.404-1.02l-1.106-4.637 3.62-3.102c.635-.544.297-1.584-.536-1.65l-4.752-.382-1.831-4.401z" clip-rule="evenodd" />
            </svg>
            {{ t(primaryAction.text) }}
          </div>
        </a>

        <!-- Secondary action button -->
        <a 
          v-if="secondaryAction"
          :href="secondaryAction.url"
          :target="secondaryAction.external ? '_blank' : '_self'"
          :rel="secondaryAction.external ? 'noopener noreferrer' : ''"
          :class="`${getButtonClasses(secondaryAction.type)} group w-full sm:w-auto min-w-[200px] text-center touch-manipulation relative overflow-hidden`"
        >
          <div class="absolute inset-0 bg-gradient-to-r from-blue-100 to-indigo-100 opacity-0 group-hover:opacity-100 transition-opacity duration-300"></div>
          <div class="relative">
            {{ t(secondaryAction.text) }}
          </div>
        </a>
      </div>

      <!-- Banner Image -->
      <div class="mt-10 sm:mt-12 md:mt-16 max-w-4xl mx-auto px-2 animate-fade-in-up animation-delay-900">
        <div class="group relative rounded-lg sm:rounded-xl overflow-hidden shadow-xl sm:shadow-2xl transition-all duration-500 hover:shadow-3xl hover:-translate-y-2">
          <div class="absolute inset-0 bg-gradient-to-br from-blue-500/10 to-purple-500/10 opacity-0 group-hover:opacity-100 transition-opacity duration-300"></div>
          <img 
            :src="bannerSrc"
            :alt="bannerAlt"
            class="w-full h-auto transition-all duration-500 group-hover:scale-105"
            :class="{ 'opacity-50': bannerLoading }"
            @error="handleBannerError"
            @load="handleBannerLoad"
            loading="lazy"
          />
          <!-- Loading placeholder -->
          <div 
            v-if="bannerLoading && !bannerError"
            class="absolute inset-0 bg-gray-100 animate-pulse flex items-center justify-center"
          >
            <div class="text-gray-400">
              <svg class="w-8 h-8 sm:w-12 sm:h-12" fill="currentColor" viewBox="0 0 20 20">
                <path fill-rule="evenodd" d="M4 3a2 2 0 00-2 2v10a2 2 0 002 2h12a2 2 0 002-2V5a2 2 0 00-2-2H4zm12 12H4l4-8 3 6 2-4 3 6z" clip-rule="evenodd" />
              </svg>
            </div>
          </div>
        </div>
      </div>

      <!-- Additional info -->
      <div class="mt-8 sm:mt-10 md:mt-12 text-xs sm:text-sm text-gray-500 px-4">
        <p>{{ t('hero.subtitle') }}</p>
      </div>
    </div>
  </section>
</template>