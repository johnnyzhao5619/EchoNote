<template>
  <footer class="bg-gray-50 border-t border-gray-200">
    <div class="max-w-7xl mx-auto px-3 sm:px-6 lg:px-8 py-6 sm:py-8">
      <div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-6 sm:gap-8">
        
        <!-- Project Info Section -->
        <div class="space-y-3 sm:space-y-4 sm:col-span-2 md:col-span-1">
          <div class="flex items-center space-x-2 sm:space-x-3">
            <div class="relative">
              <img 
                :src="logoSrc" 
                :alt="altText"
                class="h-5 w-5 sm:h-6 sm:w-6 rounded transition-opacity duration-200"
                :class="{ 'opacity-50': isLoading }"
                @error="handleLogoError"
                @load="handleLogoLoad"
                loading="lazy"
              />
              <!-- Loading indicator -->
              <div 
                v-if="isLoading && !hasError"
                class="absolute inset-0 flex items-center justify-center bg-gray-100 rounded animate-pulse"
              >
                <div class="w-2 h-2 sm:w-3 sm:h-3 bg-gray-300 rounded"></div>
              </div>
            </div>
            <h3 class="text-base sm:text-lg font-semibold text-gray-900">
              {{ projectConfig.name }}
            </h3>
          </div>
          <p class="text-gray-600 text-xs sm:text-sm leading-relaxed pr-4">
            {{ projectConfig.description }}
          </p>
        </div>

        <!-- Links Section -->
        <div class="space-y-3 sm:space-y-4">
          <h4 class="text-xs sm:text-sm font-semibold text-gray-900 uppercase tracking-wider">
            {{ t('footer.links') }}
          </h4>
          <div class="space-y-2">
            <a 
              :href="projectConfig.githubUrl"
              target="_blank"
              rel="noopener noreferrer"
              class="block text-gray-600 hover:text-blue-600 text-xs sm:text-sm transition-all duration-200 touch-manipulation py-1 hover:translate-x-1"
            >
              {{ t('footer.sourceCode') }}
            </a>
            <a 
              v-if="projectConfig.links.documentation"
              :href="projectConfig.links.documentation"
              target="_blank"
              rel="noopener noreferrer"
              class="block text-gray-600 hover:text-blue-600 text-xs sm:text-sm transition-all duration-200 touch-manipulation py-1 hover:translate-x-1"
            >
              {{ t('footer.documentation') }}
            </a>
            <a 
              v-if="projectConfig.links.download"
              :href="projectConfig.links.download"
              target="_blank"
              rel="noopener noreferrer"
              class="block text-gray-600 hover:text-blue-600 text-xs sm:text-sm transition-all duration-200 touch-manipulation py-1 hover:translate-x-1"
            >
              {{ t('footer.releases') }}
            </a>
          </div>
        </div>

        <!-- License and Copyright Section -->
        <div class="space-y-3 sm:space-y-4">
          <h4 class="text-xs sm:text-sm font-semibold text-gray-900 uppercase tracking-wider">
            {{ t('footer.legal') }}
          </h4>
          <div class="space-y-2">
            <p class="text-gray-600 text-xs sm:text-sm leading-relaxed">
              {{ t('footer.license') }}
              <a 
                :href="licenseInfo.url"
                target="_blank"
                rel="noopener noreferrer"
                class="text-blue-600 hover:text-blue-800 underline touch-manipulation"
              >
                {{ licenseInfo.name }}
              </a>
            </p>
            <p class="text-gray-600 text-xs sm:text-sm leading-relaxed">
              {{ t('footer.copyright') }} © {{ currentYear }} 
              <a 
                :href="`https://github.com/${githubConfig.owner}`"
                target="_blank"
                rel="noopener noreferrer"
                class="text-blue-600 hover:text-blue-800 underline touch-manipulation"
              >
                {{ githubConfig.owner }}
              </a>
            </p>
          </div>
        </div>
      </div>

      <!-- Bottom Section -->
      <div class="mt-6 sm:mt-8 pt-4 sm:pt-6 border-t border-gray-200">
        <div class="flex flex-col space-y-3 sm:space-y-4 md:flex-row md:justify-between md:items-center md:space-y-0">
          <div class="flex flex-col sm:flex-row sm:items-center space-y-2 sm:space-y-0 sm:space-x-4 text-xs sm:text-sm text-gray-500">
            <span>{{ t('footer.builtWith') }}</span>
            <div class="flex flex-wrap items-center gap-1 sm:gap-2">
              <template v-for="(tech, index) in techStack" :key="tech">
                <span>{{ tech }}</span>
                <span v-if="index < techStack.length - 1" class="hidden sm:inline">•</span>
              </template>
            </div>
          </div>
          
          <div class="flex items-center justify-center sm:justify-start">
            <!-- GitHub Star Button -->
            <a 
              :href="projectConfig.githubUrl"
              target="_blank"
              rel="noopener noreferrer"
              class="group inline-flex items-center space-x-2 text-xs sm:text-sm text-gray-600 hover:text-yellow-600 transition-all duration-200 touch-manipulation py-2 px-3 rounded-md hover:bg-yellow-50 hover:scale-105"
            >
              <div class="transition-transform duration-200 group-hover:rotate-12 group-hover:scale-110">
                <StarIcon />
              </div>
              <span>{{ t('footer.starOnGitHub') }}</span>
            </a>
          </div>
        </div>
      </div>
    </div>
  </footer>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import StarIcon from './icons/StarIcon.vue'
import { projectConfig, githubConfig, techStack, licenseInfo } from '../config/project'
import { useLogo } from '../composables/useLogo'

const { t } = useI18n()
const { logoSrc, isLoading, hasError, altText, handleLogoError, handleLogoLoad } = useLogo()

// Current year for copyright
const currentYear = computed(() => new Date().getFullYear())
</script>