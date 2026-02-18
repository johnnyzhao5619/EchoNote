<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import LanguageSwitcher from './LanguageSwitcher.vue'
import GitHubIcon from './icons/GitHubIcon.vue'
import { projectConfig } from '../config/project'
import { useLogo } from '../composables/useLogo'

const { t } = useI18n()
const { logoSrc, isLoading, hasError, altText, handleLogoError, handleLogoLoad } = useLogo()

const isMobileMenuOpen = ref(false)
const isMoreMenuOpen = ref(false)
const headerRef = ref<HTMLElement | null>(null)

const sectionNav = computed(() => [
  { href: '#features', label: t('nav.features') },
  { href: '#how-it-works', label: t('nav.howItWorks') },
  { href: '#github-stats', label: t('nav.stats') },
])

const resourceNav = computed(() => {
  const items = [
    { href: projectConfig.links.documentation, label: t('nav.documentation') },
    { href: projectConfig.links.issues, label: t('nav.issues') },
    { href: projectConfig.links.download, label: t('nav.releases') },
  ]
  return items.filter((item): item is { href: string; label: string } => Boolean(item.href))
})

const primaryResourceNav = computed(() => resourceNav.value[0] || null)
const overflowResourceNav = computed(() => resourceNav.value.slice(1))
const compactMoreItems = computed(() => [
  ...sectionNav.value.map((item) => ({ ...item, external: false })),
  ...overflowResourceNav.value.map((item) => ({ ...item, external: true })),
])

const toggleMobileMenu = () => {
  isMobileMenuOpen.value = !isMobileMenuOpen.value
  if (isMobileMenuOpen.value) {
    isMoreMenuOpen.value = false
  }
}

const closeMobileMenu = () => {
  isMobileMenuOpen.value = false
}

const toggleMoreMenu = () => {
  isMoreMenuOpen.value = !isMoreMenuOpen.value
}

const closeMoreMenu = () => {
  isMoreMenuOpen.value = false
}

let lgMediaQuery: MediaQueryList | null = null
let xlMediaQuery: MediaQueryList | null = null

const handleBreakpointChange = () => {
  if (lgMediaQuery?.matches) {
    closeMobileMenu()
  }
  if (xlMediaQuery?.matches || !lgMediaQuery?.matches) {
    closeMoreMenu()
  }
}

const handleClickOutside = (event: Event) => {
  const target = event.target as HTMLElement
  if (headerRef.value && !headerRef.value.contains(target)) {
    if (isMobileMenuOpen.value) {
      closeMobileMenu()
    }
    if (isMoreMenuOpen.value) {
      closeMoreMenu()
    }
  }
}

const handleKeydown = (event: KeyboardEvent) => {
  if (event.key === 'Escape') {
    closeMobileMenu()
    closeMoreMenu()
  }
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
  document.addEventListener('keydown', handleKeydown)

  lgMediaQuery = window.matchMedia('(min-width: 1024px)')
  xlMediaQuery = window.matchMedia('(min-width: 1280px)')
  lgMediaQuery.addEventListener('change', handleBreakpointChange)
  xlMediaQuery.addEventListener('change', handleBreakpointChange)
  handleBreakpointChange()
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
  document.removeEventListener('keydown', handleKeydown)
  lgMediaQuery?.removeEventListener('change', handleBreakpointChange)
  xlMediaQuery?.removeEventListener('change', handleBreakpointChange)
})
</script>

<template>
  <header
    id="top"
    ref="headerRef"
    class="sticky top-0 z-50 border-b border-slate-200/80 bg-white/90 shadow-sm backdrop-blur"
  >
    <a href="#main-content" class="skip-link">{{ t('header.skipToContent') }}</a>

    <div class="site-container">
      <div class="flex h-16 items-center justify-between gap-4">
        <a href="#top" class="flex items-center gap-3 text-slate-900" @click="closeMobileMenu">
          <div class="relative">
            <img
              :src="logoSrc"
              :alt="altText"
              class="h-8 w-8 rounded transition-opacity duration-200"
              :class="{ 'opacity-50': isLoading }"
              @error="handleLogoError"
              @load="handleLogoLoad"
              loading="eager"
            />
            <div
              v-if="isLoading && !hasError"
              class="absolute inset-0 flex items-center justify-center rounded bg-slate-100"
            >
              <div class="h-3 w-3 animate-pulse rounded bg-slate-300"></div>
            </div>
          </div>
          <span class="text-lg font-bold tracking-tight">{{ projectConfig.name }}</span>
        </a>

        <nav class="hidden xl:flex items-center gap-1" aria-label="Primary">
          <a
            v-for="item in sectionNav"
            :key="item.href"
            :href="item.href"
            class="ui-nav-link"
          >
            {{ item.label }}
          </a>
        </nav>

        <div class="hidden lg:flex items-center gap-1">
          <a
            v-if="primaryResourceNav"
            :href="primaryResourceNav.href"
            target="_blank"
            rel="noopener noreferrer"
            class="ui-nav-link xl:hidden"
          >
            {{ primaryResourceNav.label }}
          </a>

          <a
            v-for="item in resourceNav"
            :key="item.href"
            :href="item.href"
            target="_blank"
            rel="noopener noreferrer"
            class="hidden ui-nav-link xl:inline-flex"
          >
            {{ item.label }}
          </a>

          <div v-if="compactMoreItems.length > 0" class="relative xl:hidden">
            <button
              @click="toggleMoreMenu"
              type="button"
              class="inline-flex items-center ui-nav-link"
              :aria-expanded="isMoreMenuOpen"
              aria-controls="desktop-more-menu"
            >
              {{ t('header.more') }}
              <svg
                class="ml-1 h-4 w-4 transition-transform"
                :class="{ 'rotate-180': isMoreMenuOpen }"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
              </svg>
            </button>

            <div
              v-if="isMoreMenuOpen"
              id="desktop-more-menu"
              class="absolute right-0 z-20 mt-1 w-44 overflow-hidden rounded-lg border border-slate-200 bg-white py-1 shadow-lg"
            >
              <a
                v-for="item in compactMoreItems"
                :key="`overflow-${item.href}`"
                :href="item.href"
                :target="item.external ? '_blank' : undefined"
                :rel="item.external ? 'noopener noreferrer' : undefined"
                class="block whitespace-nowrap ui-mobile-nav-link"
                @click="closeMoreMenu"
              >
                {{ item.label }}
              </a>
            </div>
          </div>

          <a
            :href="projectConfig.githubUrl"
            target="_blank"
            rel="noopener noreferrer"
            class="group inline-flex items-center gap-2 whitespace-nowrap rounded-md border border-slate-200 px-2.5 py-2 text-sm font-semibold text-slate-700 transition-colors hover:border-slate-300 hover:bg-slate-100 hover:text-slate-900"
          >
            <GitHubIcon />
            <span>{{ t('hero.viewOnGitHub') }}</span>
          </a>

          <LanguageSwitcher />
        </div>

        <button
          @click="toggleMobileMenu"
          class="lg:hidden rounded-md p-2 text-slate-600 transition-colors hover:bg-slate-100 hover:text-slate-900"
          :aria-label="t('header.toggleMenu')"
          :aria-expanded="isMobileMenuOpen"
          aria-controls="mobile-nav"
        >
          <svg class="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
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

      <div v-if="isMobileMenuOpen" id="mobile-nav" class="border-t border-slate-200 py-4 lg:hidden">
        <nav class="flex flex-col gap-2" aria-label="Mobile">
          <a
            v-for="item in sectionNav"
            :key="`mobile-${item.href}`"
            :href="item.href"
            class="ui-mobile-nav-link"
            @click="closeMobileMenu"
          >
            {{ item.label }}
          </a>

          <a
            v-for="item in resourceNav"
            :key="`mobile-resource-${item.href}`"
            :href="item.href"
            target="_blank"
            rel="noopener noreferrer"
            class="ui-mobile-nav-link"
            @click="closeMobileMenu"
          >
            {{ item.label }}
          </a>

          <a
            :href="projectConfig.githubUrl"
            target="_blank"
            rel="noopener noreferrer"
            class="inline-flex items-center gap-2 ui-mobile-nav-link text-slate-800 font-semibold"
            @click="closeMobileMenu"
          >
            <GitHubIcon />
            <span>{{ t('hero.viewOnGitHub') }}</span>
          </a>

          <div class="px-2 pt-2">
            <LanguageSwitcher />
          </div>
        </nav>
      </div>
    </div>
  </header>
</template>
