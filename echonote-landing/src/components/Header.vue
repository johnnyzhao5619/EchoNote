<template>
  <header class="bg-white shadow-sm border-b border-gray-200 sticky top-0 z-50">
    <div class="max-w-7xl mx-auto px-3 sm:px-6 lg:px-8">
      <div class="flex justify-between items-center h-14 sm:h-16">
        <!-- Logo and Project Name -->
        <div class="flex items-center space-x-2 sm:space-x-3">
          <div class="relative">
            <img 
              :src="logoSrc" 
              :alt="altText"
              class="h-7 w-7 sm:h-8 sm:w-8 rounded transition-opacity duration-200"
              :class="{ 'opacity-50': isLoading }"
              @error="handleLogoError"
              @load="handleLogoLoad"
              loading="eager"
            />
            <!-- Loading indicator -->
            <div 
              v-if="isLoading && !hasError"
              class="absolute inset-0 flex items-center justify-center bg-gray-100 rounded animate-pulse"
            >
              <div class="w-3 h-3 sm:w-4 sm:h-4 bg-gray-300 rounded"></div>
            </div>
          </div>
          <h1 class="text-lg sm:text-xl font-bold text-gray-900 truncate">
            {{ projectConfig.name }}
          </h1>
        </div>

        <!-- Desktop Navigation -->
        <nav class="hidden md:flex items-center space-x-6">
          <a 
            :href="projectConfig.githubUrl"
            target="_blank"
            rel="noopener noreferrer"
            class="group flex items-center space-x-2 px-3 py-2 text-gray-600 hover:text-gray-900 hover:bg-gray-50 rounded-lg transition-all duration-200 transform hover:scale-105"
          >
            <div class="transition-transform duration-200 group-hover:rotate-12">
              <GitHubIcon />
            </div>
            <span class="font-medium">{{ t('header.github') }}</span>
          </a>
          
          <div class="transform transition-all duration-200 hover:scale-105">
            <LanguageSwitcher />
          </div>
        </nav>

        <!-- Mobile Menu Button -->
        <div class="md:hidden">
          <button
            @click="toggleMobileMenu"
            class="p-2 text-gray-600 hover:text-gray-900 hover:bg-gray-100 focus:outline-none focus:text-gray-900 focus:bg-gray-100 rounded-md transition-all duration-200 touch-manipulation"
            :aria-label="t('header.toggleMenu')"
            :aria-expanded="isMobileMenuOpen"
          >
            <svg class="w-5 h-5 sm:w-6 sm:h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path 
                v-if="!isMobileMenuOpen"
                stroke-linecap="round" 
                stroke-linejoin="round" 
                stroke-width="2" 
                d="M4 6h16M4 12h16M4 18h16"
              />
              <path 
                v-else
                stroke-linecap="round" 
                stroke-linejoin="round" 
                stroke-width="2" 
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        </div>
      </div>

      <!-- Mobile Navigation Menu -->
      <div 
        v-if="isMobileMenuOpen"
        class="md:hidden border-t border-gray-200 py-3 bg-gray-50"
      >
        <div class="flex flex-col space-y-3 px-1">
          <a 
            :href="projectConfig.githubUrl"
            target="_blank"
            rel="noopener noreferrer"
            class="flex items-center space-x-3 p-3 text-gray-700 hover:text-gray-900 hover:bg-white rounded-lg transition-all duration-200 touch-manipulation"
            @click="closeMobileMenu"
          >
            <GitHubIcon />
            <span class="font-medium">{{ t('header.github') }}</span>
          </a>
          
          <div class="px-3 py-2">
            <LanguageSwitcher />
          </div>
        </div>
      </div>
    </div>
  </header>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import LanguageSwitcher from './LanguageSwitcher.vue'
import GitHubIcon from './icons/GitHubIcon.vue'
import { projectConfig } from '../config/project'
import { useLogo } from '../composables/useLogo'

const { t } = useI18n()
const { logoSrc, isLoading, hasError, altText, handleLogoError, handleLogoLoad } = useLogo()

// Mobile menu state
const isMobileMenuOpen = ref(false)

const toggleMobileMenu = () => {
  isMobileMenuOpen.value = !isMobileMenuOpen.value
}

const closeMobileMenu = () => {
  isMobileMenuOpen.value = false
}

// Close mobile menu when clicking outside
const handleClickOutside = (event: Event) => {
  if (isMobileMenuOpen.value) {
    const target = event.target as HTMLElement
    const header = document.querySelector('header')
    if (header && !header.contains(target)) {
      closeMobileMenu()
    }
  }
}

// Properly manage event listeners
onMounted(() => {
  document.addEventListener('click', handleClickOutside)
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
})
</script>