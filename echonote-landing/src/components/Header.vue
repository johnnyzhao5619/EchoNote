<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { projectConfig } from '../config/project'
import { useProjectLinks } from '../composables/useProjectLinks'
import LanguageSwitcher from './LanguageSwitcher.vue'
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
    class="sticky top-0 z-50 border-b border-slate-200/70 bg-white/92 backdrop-blur"
  >
    <a href="#main-content" class="skip-link">{{ t('header.skipToContent') }}</a>

    <div class="site-container">
      <div class="flex h-16 items-center justify-between gap-4">
        <a href="#top" class="inline-flex items-center gap-3 text-slate-900" @click="closeMobileMenu">
          <Logo class-name="h-8 w-8" loading="eager" />
          <span class="text-base font-semibold tracking-tight sm:text-lg">{{ projectConfig.name }}</span>
        </a>

        <nav class="hidden items-center gap-1 lg:flex" aria-label="Primary">
          <a v-for="item in sectionNav" :key="item.id" :href="item.href" class="ui-nav-link">
            {{ item.label }}
          </a>
          <div class="mx-1 h-4 w-px bg-slate-200"></div>
          <a
            v-for="item in headerResourceNav"
            :key="item.key"
            :href="item.href"
            target="_blank"
            rel="noopener noreferrer"
            class="ui-nav-link"
          >
            {{ item.label }}
          </a>
        </nav>

        <div class="hidden items-center gap-3 lg:flex">
          <LanguageSwitcher />
          <a
            :href="projectConfig.githubUrl"
            target="_blank"
            rel="noopener noreferrer"
            class="ui-ghost-action"
          >
            <GitHubIcon />
            <span>{{ t('hero.viewOnGitHub') }}</span>
          </a>
        </div>

        <button
          type="button"
          class="inline-flex h-10 w-10 items-center justify-center rounded-lg border border-slate-200 text-slate-700 transition hover:border-slate-300 hover:bg-slate-50 lg:hidden"
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

      <div v-if="isMobileMenuOpen" id="mobile-nav" class="border-t border-slate-200/70 py-4 lg:hidden">
        <nav class="flex flex-col gap-1" aria-label="Mobile">
          <a
            v-for="item in mobileNavItems"
            :key="`mobile-${item.href}`"
            :href="item.href"
            :target="item.external ? '_blank' : undefined"
            :rel="item.external ? 'noopener noreferrer' : undefined"
            class="ui-mobile-nav-link"
            @click="closeMobileMenu"
          >
            {{ item.label }}
          </a>

          <a
            :href="projectConfig.githubUrl"
            target="_blank"
            rel="noopener noreferrer"
            class="mt-1 inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-semibold text-slate-800 transition hover:bg-slate-100"
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
