<script setup lang="ts">
import { computed, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useGitHubApi } from '../composables/useGitHubApi'
import { githubConfig, projectConfig } from '../config/project'
import GitHubIcon from './icons/GitHubIcon.vue'

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
  showRelease: true,
})

const [owner, repo] = props.repository.split('/')
if (!owner || !repo) {
  throw new Error('Invalid repository format. Expected "owner/repo"')
}

const { stats, loading, error, fetchAll, refresh, repository: repoData, latestRelease } =
  useGitHubApi(owner, repo)

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
      tone: 'bg-amber-50 border-amber-200 text-amber-700',
    },
    {
      id: 'forks',
      icon: '🍴',
      label: t('github.forks'),
      value: formatNumber(stats.value.forks),
      tone: 'bg-sky-50 border-sky-200 text-sky-700',
    },
    {
      id: 'issues',
      icon: '🐛',
      label: t('github.issues'),
      value: formatNumber(stats.value.issues),
      tone: 'bg-rose-50 border-rose-200 text-rose-700',
    },
  ]
})

let refreshTimer: ReturnType<typeof setInterval> | null = null

onMounted(() => {
  void fetchAll()

  if (props.refreshInterval > 0) {
    refreshTimer = setInterval(() => {
      void refresh()
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
        <h2 id="github-title" class="mb-3 text-3xl font-semibold text-slate-900 sm:text-4xl">
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
        <div class="inline-flex items-center rounded-lg border border-slate-200 bg-white px-5 py-3 text-sm text-slate-600 shadow-sm">
          <svg class="mr-2 h-4 w-4 animate-spin text-blue-600" viewBox="0 0 24 24" fill="none">
            <circle class="opacity-30" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="opacity-90" d="M22 12a10 10 0 00-10-10" stroke="currentColor" stroke-width="4" stroke-linecap="round"></path>
          </svg>
          {{ t('github.loading') }}
        </div>
      </div>

      <div v-else-if="error" class="text-center">
        <div class="inline-flex items-center rounded-lg border border-rose-200 bg-rose-50 px-6 py-3 text-rose-700">
          {{ t('github.error') }}
        </div>
      </div>

      <div v-else-if="stats" class="space-y-8">
        <div class="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <article
            v-for="item in statsItems"
            :key="item.id"
            :class="['rounded-xl border p-5 text-center transition hover:-translate-y-0.5 hover:shadow-md', item.tone]"
          >
            <div class="mb-2 text-2xl">{{ item.icon }}</div>
            <div class="text-3xl font-semibold">{{ item.value }}</div>
            <div class="mt-1 text-sm text-slate-600">{{ item.label }}</div>
          </article>
        </div>

        <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
          <article class="landing-card p-6">
            <h3 class="mb-3 text-lg font-semibold text-slate-900">
              {{ t('github.repository') }}
            </h3>
            <p class="mb-4 text-sm leading-relaxed text-slate-600 sm:text-base">
              {{ repoData?.description }}
            </p>
            <div class="flex flex-wrap gap-2">
              <span
                v-if="showLanguage && repoData?.language"
                class="inline-flex items-center rounded-full bg-blue-100 px-3 py-1 text-xs font-medium text-blue-800"
              >
                {{ repoData.language }}
              </span>
              <span
                v-if="repoData?.license?.name"
                class="inline-flex items-center rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-700"
              >
                {{ t('github.license') }}: {{ repoData.license.name }}
              </span>
              <span
                class="inline-flex items-center rounded-full bg-emerald-100 px-3 py-1 text-xs font-medium text-emerald-800"
              >
                {{ t('github.openSource') }}
              </span>
            </div>
            <p v-if="repoData?.updated_at" class="mt-4 text-xs text-slate-500 sm:text-sm">
              {{ t('github.updatedOn') }} {{ formatDate(repoData.updated_at) }}
            </p>
          </article>

          <article v-if="showRelease" class="landing-card p-6">
            <h3 class="mb-3 text-lg font-semibold text-slate-900">
              {{ t('github.latestRelease') }}
            </h3>
            <div v-if="latestRelease" class="space-y-2">
              <p class="text-2xl font-semibold text-blue-700">
                {{ latestRelease.tag_name }}
              </p>
              <p class="text-sm text-slate-600">
                {{ t('github.released') }} {{ formatDate(latestRelease.published_at) }}
              </p>
              <a
                :href="latestRelease.html_url"
                target="_blank"
                rel="noopener noreferrer"
                class="inline-flex items-center text-sm font-medium text-blue-700 hover:text-blue-900"
              >
                {{ t('github.viewRelease') }}
                <svg class="ml-1 h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                </svg>
              </a>
            </div>
            <p v-else class="text-sm text-slate-500">
              {{ t('github.noReleases') }}
            </p>
          </article>
        </div>

        <div class="text-center">
          <a :href="projectConfig.githubUrl" target="_blank" rel="noopener noreferrer" class="ui-primary-action">
            <GitHubIcon icon-class="h-5 w-5" />
            <span>{{ t('github.viewOnGitHub') }}</span>
          </a>
        </div>
      </div>
    </div>
  </section>
</template>
