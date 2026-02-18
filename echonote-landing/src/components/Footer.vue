<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import StarIcon from './icons/StarIcon.vue'
import { projectConfig, githubConfig, licenseInfo } from '../config/project'
import { useLogo } from '../composables/useLogo'

const { t } = useI18n()
const { logoSrc, isLoading, hasError, altText, handleLogoError, handleLogoLoad } = useLogo()

const currentYear = computed(() => new Date().getFullYear())

const openSourceLinks = computed(() => {
  const items = [
    { label: t('footer.sourceCode'), href: projectConfig.githubUrl },
    { label: t('footer.documentation'), href: projectConfig.links.documentation },
    { label: t('footer.releases'), href: projectConfig.links.download },
    { label: t('footer.issues'), href: projectConfig.links.issues },
    { label: t('footer.contributing'), href: projectConfig.links.contributing },
    { label: t('footer.discussions'), href: projectConfig.links.discussions },
  ]
  return items.filter((item): item is { label: string; href: string } => Boolean(item.href))
})
</script>

<template>
  <footer class="border-t border-slate-200 bg-white">
    <div class="site-container py-10">
      <div class="grid grid-cols-1 gap-8 md:grid-cols-3">
        <div class="space-y-4">
          <div class="flex items-center gap-3">
            <div class="relative">
              <img
                :src="logoSrc"
                :alt="altText"
                class="h-6 w-6 rounded transition-opacity duration-200"
                :class="{ 'opacity-50': isLoading }"
                @error="handleLogoError"
                @load="handleLogoLoad"
                loading="lazy"
              />
              <div
                v-if="isLoading && !hasError"
                class="absolute inset-0 flex items-center justify-center rounded bg-slate-100"
              >
                <div class="h-2.5 w-2.5 animate-pulse rounded bg-slate-300"></div>
              </div>
            </div>
            <h3 class="text-base font-semibold text-slate-900 sm:text-lg">
              {{ projectConfig.name }}
            </h3>
          </div>
          <p class="max-w-sm text-sm leading-relaxed text-slate-600">
            {{ projectConfig.description }}
          </p>
        </div>

        <div class="space-y-4">
          <h4 class="text-xs font-semibold uppercase tracking-wider text-slate-900">
            {{ t('footer.openSource') }}
          </h4>
          <nav class="grid grid-cols-2 gap-x-4 gap-y-2" aria-label="Open source resources">
            <a
              v-for="item in openSourceLinks"
              :key="item.href"
              :href="item.href"
              target="_blank"
              rel="noopener noreferrer"
              class="text-sm text-slate-600 transition-colors hover:text-blue-600"
            >
              {{ item.label }}
            </a>
          </nav>
        </div>

        <div class="space-y-4">
          <h4 class="text-xs font-semibold uppercase tracking-wider text-slate-900">
            {{ t('footer.legal') }}
          </h4>
          <p class="text-sm leading-relaxed text-slate-600">
            {{ t('footer.license') }}
            <a
              :href="projectConfig.links.license || licenseInfo.url"
              target="_blank"
              rel="noopener noreferrer"
              class="ui-inline-link"
            >
              {{ licenseInfo.name }}
            </a>
          </p>
          <p class="text-sm leading-relaxed text-slate-600">
            {{ t('footer.copyright') }} © {{ currentYear }}
            <a
              :href="`https://github.com/${githubConfig.owner}`"
              target="_blank"
              rel="noopener noreferrer"
              class="ui-inline-link"
            >
              {{ githubConfig.owner }}
            </a>
          </p>
        </div>
      </div>

      <div class="mt-8 flex justify-end border-t border-slate-200 pt-6">
        <a
          :href="projectConfig.githubUrl"
          target="_blank"
          rel="noopener noreferrer"
          class="group inline-flex items-center gap-2 rounded-md px-3 py-2 text-sm text-slate-600 transition-all duration-200 hover:bg-yellow-50 hover:text-yellow-700"
        >
          <span class="transition-transform duration-200 group-hover:scale-110 group-hover:rotate-12">
            <StarIcon />
          </span>
          <span>{{ t('footer.starOnGitHub') }}</span>
        </a>
      </div>
    </div>
  </footer>
</template>
