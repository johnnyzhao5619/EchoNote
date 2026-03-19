<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { projectConfig } from '../config/project'
import { useProjectLinks } from '../composables/useProjectLinks'
import LanguageSwitcher from './LanguageSwitcher.vue'
import ThemeToggle from './ThemeToggle.vue'
import GitHubIcon from './icons/GitHubIcon.vue'
import Logo from './Logo.vue'

const { t } = useI18n()
const { sectionNav, headerResourceNav } = useProjectLinks()

const isMobileMenuOpen = ref(false)
const headerRef = ref<HTMLElement | null>(null)

const mobileNavItems = computed(() => [
  ...sectionNav.value.map((item) => ({ ...item, external: false })),
  ...headerResourceNav.value.map((item) => ({ ...item, external: true })),
])

const closeMobileMenu = () => {
  isMobileMenuOpen.value = false
}

const toggleMobileMenu = () => {
  isMobileMenuOpen.value = !isMobileMenuOpen.value
}

const handleClickOutside = (event: Event) => {
  const target = event.target as HTMLElement
  if (headerRef.value && !headerRef.value.contains(target)) {
    closeMobileMenu()
  }
}

const handleKeydown = (event: KeyboardEvent) => {
  if (event.key === 'Escape') {
    closeMobileMenu()
  }
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
  document.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
  document.removeEventListener('keydown', handleKeydown)
})
</script>

<template>
  <header
    id="top"
    ref="headerRef"
    class="sticky top-0 z-50 border-b border-gray-200/70 dark:border-white/10 bg-white/92 dark:bg-gray-900/90 backdrop-blur transition-colors duration-300"
  >
    <a href="#main-content" class="skip-link">{{ t('header.skipToContent') }}</a>

    <div class="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
      <div class="flex h-16 items-center justify-between gap-4">
        <a
          href="#top"
          class="inline-flex items-center gap-3 text-gray-900 dark:text-white transition-colors"
          @click="closeMobileMenu"
        >
          <Logo class-name="h-8 w-8" loading="eager" />
          <span class="text-base font-semibold tracking-tight sm:text-lg">{{
            projectConfig.name
          }}</span>
        </a>

        <nav class="hidden items-center gap-1 lg:flex" aria-label="Primary">
          <a v-for="item in sectionNav" :key="item.id" :href="item.href" class="text-sm font-medium text-gray-600 dark:text-gray-300 hover:text-blue-600 dark:hover:text-blue-400 px-3 py-2 transition-colors">
            {{ item.label }}
          </a>
          <div class="mx-1 h-4 w-px bg-gray-200 dark:bg-gray-700"></div>
          <a
            v-for="item in headerResourceNav"
            :key="item.key"
            :href="item.href"
            target="_blank"
            rel="noopener noreferrer"
            class="text-sm font-medium text-gray-600 dark:text-gray-300 hover:text-blue-600 dark:hover:text-blue-400 px-3 py-2 transition-colors"
          >
            {{ item.label }}
          </a>
        </nav>

        <div class="hidden items-center gap-2 lg:flex">
          <ThemeToggle />
          <LanguageSwitcher />
          <div class="w-px h-6 bg-gray-200 dark:bg-gray-700 mx-2"></div>
          <a
            :href="projectConfig.githubUrl"
            target="_blank"
            rel="noopener noreferrer"
            class="text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white transition-colors"
            aria-label="GitHub"
          >
            <GitHubIcon class="w-5 h-5" />
          </a>
        </div>

        <button
          type="button"
          class="inline-flex h-10 w-10 items-center justify-center rounded-lg border border-gray-200 dark:border-gray-700 text-gray-700 dark:text-gray-300 transition hover:border-gray-300 dark:hover:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-800 lg:hidden"
          :aria-label="t('header.toggleMenu')"
          :aria-expanded="isMobileMenuOpen"
          aria-controls="mobile-nav"
          @click="toggleMobileMenu"
        >
          <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              v-if="!isMobileMenuOpen"
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M4 7h16M4 12h16M4 17h16"
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

      <div
        v-if="isMobileMenuOpen"
        id="mobile-nav"
        class="border-t border-gray-200/70 dark:border-white/10 py-4 lg:hidden"
      >
        <nav class="flex flex-col gap-2" aria-label="Mobile">
          <a
            v-for="item in mobileNavItems"
            :key="`mobile-${item.href}`"
            :href="item.href"
            :target="item.external ? '_blank' : undefined"
            :rel="item.external ? 'noopener noreferrer' : undefined"
            class="block rounded-md px-3 py-2 text-base font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 hover:text-gray-900 dark:hover:text-white"
            @click="closeMobileMenu"
          >
            {{ item.label }}
          </a>

          <a
            :href="projectConfig.githubUrl"
            target="_blank"
            rel="noopener noreferrer"
            class="mt-2 inline-flex items-center gap-2 rounded-md px-3 py-2 text-base font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 hover:text-gray-900 dark:hover:text-white"
            @click="closeMobileMenu"
          >
            <GitHubIcon class="w-5 h-5" />
            <span>{{ t('hero.viewOnGitHub') }}</span>
          </a>

          <div class="flex items-center gap-4 px-3 pt-4 pb-2 border-t border-gray-200 dark:border-gray-700 mt-2">
            <LanguageSwitcher />
            <ThemeToggle />
          </div>
        </nav>
      </div>
    </div>
  </header>
</template>
