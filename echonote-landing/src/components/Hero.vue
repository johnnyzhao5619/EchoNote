<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { githubConfig, projectConfig } from '../config/project'
import { useGitHubApi } from '../composables/useGitHubApi'
import { useProjectLinks } from '../composables/useProjectLinks'
import GitHubIcon from './icons/GitHubIcon.vue'

interface Props {
  title?: string
  description?: string
}

const props = defineProps<Props>()
const { t } = useI18n()
const { heroQuickLinks } = useProjectLinks()
const { latestRelease, fetchAll } = useGitHubApi(githubConfig.owner, githubConfig.repo)

onMounted(() => {
  void fetchAll()
})

const heroTitle = computed(() => props.title || t('hero.headline'))
const heroDescription = computed(() => props.description || t('hero.description'))
const releaseBadge = computed(() =>
  t('hero.releaseBadge', { version: latestRelease.value?.tag_name ?? 'latest' }),
)
</script>

<template>
  <header class="hero-shell section-shell" aria-labelledby="hero-heading">
    <div class="site-container">
      <div class="grid items-center gap-10 lg:grid-cols-[1.04fr_0.96fr]">
        <div class="text-center lg:text-left">
          <p
            class="mb-5 inline-flex items-center gap-2 rounded-full border border-blue-200/70 bg-blue-50 px-4 py-1 text-xs font-semibold uppercase tracking-wider text-blue-700"
          >
            <span class="h-1.5 w-1.5 rounded-full bg-blue-500"></span>
            {{ releaseBadge }}
          </p>

          <h1 id="hero-heading" class="mb-5 text-balance text-4xl font-semibold leading-tight text-slate-950 sm:text-5xl lg:text-6xl">
            {{ heroTitle }}
          </h1>

          <p class="mx-auto mb-8 max-w-xl text-lg leading-relaxed text-slate-600 lg:mx-0">
            {{ heroDescription }}
          </p>

          <div class="mb-8 flex flex-col gap-3 sm:flex-row sm:items-center lg:justify-start">
            <a
              :href="projectConfig.githubUrl"
              target="_blank"
              rel="noopener noreferrer"
              class="ui-primary-action"
              aria-label="View EchoNote on GitHub"
            >
              <GitHubIcon icon-class="h-5 w-5" />
              <span>{{ t('hero.viewOnGitHub') }}</span>
            </a>
            <a href="#features" class="ui-secondary-action">
              {{ t('hero.learnMore') }}
            </a>
          </div>

          <div class="flex flex-wrap items-center justify-center gap-2 lg:justify-start">
            <a
              v-for="link in heroQuickLinks"
              :key="link.key"
              :href="link.href"
              target="_blank"
              rel="noopener noreferrer"
              class="ui-chip-link"
            >
              {{ link.label }}
            </a>
          </div>
        </div>

        <div class="hero-preview-wrap">
          <div class="hero-preview-header">
            <div class="hero-dot bg-rose-400"></div>
            <div class="hero-dot bg-amber-400"></div>
            <div class="hero-dot bg-emerald-400"></div>
          </div>
          <img
            src="/Banner.png"
            :alt="t('hero.previewAlt')"
            class="hero-preview-image"
            loading="eager"
          />
        </div>
      </div>
    </div>
  </header>
</template>
