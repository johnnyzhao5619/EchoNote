<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import StarIcon from './icons/StarIcon.vue'
import { projectConfig, githubConfig, licenseInfo } from '../config/project'
import { useProjectLinks } from '../composables/useProjectLinks'

const { t } = useI18n()
const { footerOpenSourceLinks } = useProjectLinks()

const currentYear = computed(() => new Date().getFullYear())
</script>

<template>
  <footer class="border-t border-slate-200/80 bg-white/90 backdrop-blur">
    <div class="site-container py-10">
      <div class="grid grid-cols-1 gap-8 md:grid-cols-3">
        <div class="space-y-4">
          <div class="flex items-center gap-3">
            <img
              src="/Logo.png"
              :alt="`${projectConfig.name} logo`"
              class="h-7 w-7 rounded-lg border border-slate-200"
              loading="lazy"
            />
            <h3 class="text-base font-semibold text-slate-900 sm:text-lg">
              {{ projectConfig.name }}
            </h3>
          </div>
          <p class="max-w-sm text-sm leading-relaxed text-slate-600">
            {{ t('footer.summary') }}
          </p>
        </div>

        <div class="space-y-4">
          <h4 class="text-xs font-semibold uppercase tracking-wider text-slate-900">
            {{ t('footer.openSource') }}
          </h4>
          <nav class="grid grid-cols-2 gap-x-4 gap-y-2" aria-label="Open source resources">
            <a
              :href="projectConfig.githubUrl"
              target="_blank"
              rel="noopener noreferrer"
              class="text-sm text-slate-600 transition-colors hover:text-blue-700"
            >
              {{ t('footer.sourceCode') }}
            </a>
            <a
              v-for="item in footerOpenSourceLinks"
              :key="item.key"
              :href="item.href"
              target="_blank"
              rel="noopener noreferrer"
              class="text-sm text-slate-600 transition-colors hover:text-blue-700"
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
          class="group inline-flex items-center gap-2 rounded-md px-3 py-2 text-sm text-slate-600 transition-all duration-200 hover:bg-amber-50 hover:text-amber-700"
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
