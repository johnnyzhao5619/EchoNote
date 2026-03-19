<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import StarIcon from './icons/StarIcon.vue'
import Logo from './Logo.vue'
import { projectConfig, githubConfig, licenseInfo } from '../config/project'
import { useProjectLinks } from '../composables/useProjectLinks'

const { t } = useI18n()
const { footerOpenSourceLinks } = useProjectLinks()

const currentYear = computed(() => new Date().getFullYear())
</script>

<template>
  <footer
    class="border-t border-gray-200/80 dark:border-white/10 bg-white/90 dark:bg-gray-900 backdrop-blur transition-colors duration-300"
  >
    <div class="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-10">
      <div class="grid grid-cols-1 gap-8 md:grid-cols-3">
        <div class="space-y-4">
          <div class="flex items-center gap-3">
            <Logo class-name="h-7 w-7" />
            <h3 class="text-base font-semibold text-gray-900 dark:text-white sm:text-lg">
              {{ projectConfig.name }}
            </h3>
          </div>
          <p class="max-w-sm text-sm leading-relaxed text-gray-600 dark:text-gray-400">
            {{ t('footer.summary') }}
          </p>
        </div>

        <div class="space-y-4">
          <h4 class="text-xs font-semibold uppercase tracking-wider text-gray-900 dark:text-white">
            {{ t('footer.openSource') }}
          </h4>
          <nav class="grid grid-cols-2 gap-x-4 gap-y-2" aria-label="Open source resources">
            <a
              :href="projectConfig.githubUrl"
              target="_blank"
              rel="noopener noreferrer"
              class="text-sm text-gray-600 dark:text-gray-400 transition-colors hover:text-blue-600 dark:hover:text-blue-400"
            >
              {{ t('footer.sourceCode') }}
            </a>
            <a
              v-for="item in footerOpenSourceLinks"
              :key="item.key"
              :href="item.href"
              target="_blank"
              rel="noopener noreferrer"
              class="text-sm text-gray-600 dark:text-gray-400 transition-colors hover:text-blue-600 dark:hover:text-blue-400"
            >
              {{ item.label }}
            </a>
          </nav>
        </div>

        <div class="space-y-4">
          <h4 class="text-xs font-semibold uppercase tracking-wider text-gray-900 dark:text-white">
            {{ t('footer.legal') }}
          </h4>
          <p class="text-sm leading-relaxed text-gray-600 dark:text-gray-400">
            {{ t('footer.license') }}
            <a
              :href="projectConfig.links.license || licenseInfo.url"
              target="_blank"
              rel="noopener noreferrer"
              class="font-medium hover:text-blue-600 dark:hover:text-blue-400 transition-colors"
            >
              {{ licenseInfo.name }}
            </a>
          </p>
          <p class="text-sm leading-relaxed text-gray-600 dark:text-gray-400">
            {{ t('footer.copyright') }} © {{ currentYear }}
            <a
              :href="`https://github.com/${githubConfig.owner}`"
              target="_blank"
              rel="noopener noreferrer"
              class="font-medium hover:text-blue-600 dark:hover:text-blue-400 transition-colors"
            >
              {{ githubConfig.owner }}
            </a>
          </p>
        </div>
      </div>

      <div class="mt-8 flex justify-end border-t border-gray-200 dark:border-gray-800 pt-6">
        <a
          :href="projectConfig.githubUrl"
          target="_blank"
          rel="noopener noreferrer"
          class="group inline-flex items-center gap-2 rounded-md px-3 py-2 text-sm text-gray-600 dark:text-gray-400 transition-all duration-200 hover:bg-gray-100 dark:hover:bg-gray-800 hover:text-gray-900 dark:hover:text-white"
        >
          <span
            class="transition-transform duration-200 group-hover:scale-110 group-hover:rotate-12"
          >
            <StarIcon />
          </span>
          <span>{{ t('footer.starOnGitHub') }}</span>
        </a>
      </div>
    </div>
  </footer>
</template>
