<script setup lang="ts">
import { onMounted, onUnmounted, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useGitHubApi } from '../composables/useGitHubApi'
import { githubConfig, projectConfig } from '../config/project'

const { t } = useI18n()

interface Props {
  repository?: string
  refreshInterval?: number
  showLanguage?: boolean
  showRelease?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  repository: `${githubConfig.owner}/${githubConfig.repo}`,
  refreshInterval: 300000,
  showLanguage: true,
  showRelease: true
})

const [owner, repo] = props.repository.split('/')
if (!owner || !repo) {
  throw new Error('Invalid repository format. Expected "owner/repo"')
}

const { stats, loading, error, fetchAll, repository: repoData, latestRelease } = useGitHubApi(owner, repo)

const compactFormatter = new Intl.NumberFormat(undefined, {
  notation: 'compact',
  maximumFractionDigits: 1,
})

const formatNumber = (num: number): string => compactFormatter.format(num)

const formatDate = (dateString: string): string =>
  new Date(dateString).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })

const statsItems = computed(() => {
  if (!stats.value) return []

  return [
    {
      id: 'stars',
      icon: '⭐',
      label: t('github.stars'),
      value: formatNumber(stats.value.stars),
      color: 'text-yellow-600',
      bgColor: 'bg-yellow-50',
      borderColor: 'border-yellow-200'
    },
    {
      id: 'forks',
      icon: '🍴',
      label: t('github.forks'),
      value: formatNumber(stats.value.forks),
      color: 'text-blue-600',
      bgColor: 'bg-blue-50',
      borderColor: 'border-blue-200'
    },
    {
      id: 'issues',
      icon: '🐛',
      label: t('github.issues'),
      value: formatNumber(stats.value.issues),
      color: 'text-rose-600',
      bgColor: 'bg-rose-50',
      borderColor: 'border-rose-200'
    }
  ]
})

let refreshTimer: ReturnType<typeof setInterval> | null = null

onMounted(() => {
  void fetchAll()

  if (props.refreshInterval > 0) {
    refreshTimer = setInterval(() => {
      void fetchAll()
    }, props.refreshInterval)
  }
})

onUnmounted(() => {
  if (refreshTimer) {
    clearInterval(refreshTimer)
  }
})
</script>

<template>
  <section id="github-stats" aria-labelledby="github-title" class="section-shell bg-slate-50">
    <div class="site-container">
      <div class="section-head mb-14">
        <h2 id="github-title" class="mb-3 text-3xl font-bold text-slate-900 sm:text-4xl">
          {{ t('github.title') }}
        </h2>
        <p class="mx-auto max-w-3xl text-lg text-slate-600">
          {{ t('github.subtitle') }}
        </p>
        <p class="mt-3 text-sm text-slate-500">
          {{ t('github.dataSource') }}
        </p>
      </div>

      <div v-if="loading && !stats" aria-live="polite" class="text-center">
        <div class="inline-flex items-center rounded-lg bg-white px-6 py-3 shadow-md">
          <svg class="-ml-1 mr-3 h-5 w-5 animate-spin text-blue-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
          {{ t('github.loading') }}
        </div>
      </div>

      <div v-else-if="error" class="text-center">
        <div class="inline-flex items-center rounded-lg border border-rose-200 bg-rose-50 px-6 py-3 text-rose-700">
          <svg class="mr-2 h-5 w-5" fill="currentColor" viewBox="0 0 20 20">
            <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clip-rule="evenodd" />
          </svg>
          {{ t('github.error') }}
        </div>
      </div>

      <div v-else-if="stats" class="space-y-10">
        <div class="grid grid-cols-1 gap-4 sm:grid-cols-3 sm:gap-6">
          <article
            v-for="item in statsItems"
            :key="item.id"
            :class="`group relative overflow-hidden rounded-xl border-2 p-5 text-center transition-all duration-300 hover:-translate-y-1 hover:shadow-lg ${item.bgColor} ${item.borderColor}`"
          >
            <div class="mb-2 text-3xl transition-transform duration-300 group-hover:scale-110">{{ item.icon }}</div>
            <div :class="`mb-1 text-3xl font-bold ${item.color}`">
              {{ item.value }}
            </div>
            <div class="text-sm font-medium text-slate-600 sm:text-base">
              {{ item.label }}
            </div>
          </article>
        </div>

        <div class="grid grid-cols-1 gap-4 md:grid-cols-2 sm:gap-6">
          <article class="rounded-xl border border-slate-200 bg-white p-5 shadow-sm transition-all duration-300 hover:border-blue-200 hover:shadow-md">
            <h3 class="mb-4 text-lg font-semibold text-slate-900 sm:text-xl">
              {{ t('github.repository') }}
            </h3>
            <p class="mb-4 text-sm leading-relaxed text-slate-600 sm:text-base">
              {{ repoData?.description }}
            </p>
            <div class="flex flex-wrap gap-2">
              <span v-if="showLanguage && repoData?.language" class="inline-flex items-center rounded-full bg-blue-100 px-3 py-1 text-xs font-medium text-blue-800 sm:text-sm">
                {{ repoData.language }}
              </span>
              <span v-if="repoData?.license?.name" class="inline-flex items-center rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-700 sm:text-sm">
                {{ t('github.license') }}: {{ repoData.license.name }}
              </span>
              <span class="inline-flex items-center rounded-full bg-emerald-100 px-3 py-1 text-xs font-medium text-emerald-800 sm:text-sm">
                {{ t('github.openSource') }}
              </span>
            </div>
            <p v-if="repoData?.updated_at" class="mt-4 text-xs text-slate-500 sm:text-sm">
              {{ t('github.updatedOn') }} {{ formatDate(repoData.updated_at) }}
            </p>
          </article>

          <article v-if="showRelease" class="rounded-xl border border-slate-200 bg-white p-5 shadow-sm transition-all duration-300 hover:border-indigo-200 hover:shadow-md">
            <h3 class="mb-4 text-lg font-semibold text-slate-900 sm:text-xl">
              {{ t('github.latestRelease') }}
            </h3>
            <div v-if="latestRelease">
              <div class="mb-2 text-2xl font-bold text-blue-600">
                {{ latestRelease.tag_name }}
              </div>
              <div class="text-sm text-slate-600">
                {{ t('github.released') }} {{ formatDate(latestRelease.published_at) }}
              </div>
              <a
                :href="latestRelease.html_url"
                target="_blank"
                rel="noopener noreferrer"
                class="mt-3 inline-flex items-center text-sm font-medium text-blue-600 hover:text-blue-800 sm:text-base"
              >
                {{ t('github.viewRelease') }}
                <svg class="ml-1 h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                </svg>
              </a>
            </div>
            <p v-else class="text-sm text-slate-500 sm:text-base">
              {{ t('github.noReleases') }}
            </p>
          </article>
        </div>

        <div class="text-center">
          <a
            :href="projectConfig.githubUrl"
            target="_blank"
            rel="noopener noreferrer"
            class="inline-flex items-center rounded-lg bg-slate-900 px-6 py-3 text-sm font-semibold text-white shadow-lg transition-all duration-200 hover:scale-[1.02] hover:bg-slate-800 hover:shadow-xl sm:px-8 sm:py-4 sm:text-base"
          >
            <svg class="mr-2 h-5 w-5 sm:mr-3 sm:h-6 sm:w-6" fill="currentColor" viewBox="0 0 20 20">
              <path fill-rule="evenodd" d="M10 0C4.477 0 0 4.484 0 10.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0110 4.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.203 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.942.359.31.678.921.678 1.856 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0020 10.017C20 4.484 15.522 0 10 0z" clip-rule="evenodd" />
            </svg>
            {{ t('github.viewOnGitHub') }}
          </a>
        </div>
      </div>
    </div>
  </section>
</template>
