<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { githubConfig, projectConfig } from '../config/project'
import { useGitHubApi } from '../composables/useGitHubApi'
import GitHubIcon from './icons/GitHubIcon.vue'
import Button from './ui/Button.vue'
import Badge from './ui/Badge.vue'

interface Props {
  title?: string
  description?: string
}

const props = defineProps<Props>()
const { t } = useI18n()
const { latestRelease, fetchAll } = useGitHubApi(githubConfig.owner, githubConfig.repo)

onMounted(() => {
  void fetchAll()
})

const heroTitle = computed(() => props.title || t('hero.title'))
const heroDescription = computed(() => props.description || t('hero.description'))
const releaseBadge = computed(() =>
  t('hero.releaseBadge', { version: latestRelease.value?.tag_name ?? '' }),
)
</script>

<template>
  <section
    class="relative pt-24 pb-16 overflow-hidden sm:pt-32 sm:pb-24 lg:pb-32"
    aria-labelledby="hero-heading"
  >
    <div class="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 text-center">
      <Badge variant="primary" class="mb-8 px-4 py-1.5 text-sm">
        {{ releaseBadge }}
      </Badge>

      <h1
        id="hero-heading"
        class="text-5xl font-extrabold tracking-tight text-gray-900 dark:text-white sm:text-6xl lg:text-7xl"
      >
        {{ heroTitle }}
      </h1>

      <p class="mx-auto mt-6 max-w-2xl text-lg leading-8 text-gray-600 dark:text-gray-300">
        {{ heroDescription }}
      </p>

      <div class="mt-10 flex flex-col sm:flex-row items-center justify-center gap-4 sm:gap-6">
        <Button
          variant="primary"
          size="lg"
          :href="projectConfig.links.download"
          class="w-full sm:w-auto"
        >
          {{ t('hero.getStarted') }}
        </Button>
        <Button
          variant="outline"
          size="lg"
          :href="projectConfig.githubUrl"
          target="_blank"
          class="w-full sm:w-auto"
        >
          <template #icon-left>
            <GitHubIcon class="w-5 h-5 mr-2" />
          </template>
          {{ t('hero.viewOnGitHub') }}
        </Button>
      </div>

      <div class="mt-16 flex justify-center">
        <div
          class="rounded-xl bg-gray-900/5 p-2 ring-1 ring-inset ring-gray-900/10 lg:-m-4 lg:rounded-2xl lg:p-4 dark:bg-white/5 dark:ring-white/10 backdrop-blur-3xl"
        >
          <img
            src="/Banner.png"
            :alt="t('hero.previewAlt')"
            class="rounded-md shadow-2xl ring-1 ring-gray-900/10 dark:ring-white/10"
            width="1200"
            height="600"
            loading="eager"
          />
        </div>
      </div>
    </div>
  </section>
</template>
