<script setup lang="ts">
import { onMounted, onUnmounted, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useGitHubApi } from '../composables/useGitHubApi'
import { githubConfig } from '../config/project'

const { t } = useI18n()

interface Props {
  repository?: string
  refreshInterval?: number
  showLanguage?: boolean
  showRelease?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  repository: `${githubConfig.owner}/${githubConfig.repo}`,
  refreshInterval: 300000, // 5 minutes
  showLanguage: true,
  showRelease: true
})

// Parse repository string
const [owner, repo] = props.repository.split('/')
if (!owner || !repo) {
  throw new Error('Invalid repository format. Expected "owner/repo"')
}
const { stats, loading, error, fetchAll, repository: repoData, latestRelease } = useGitHubApi(owner, repo)

// Format numbers for display - more efficient and cleaner
const formatNumber = (num: number): string => {
  const formatters = [
    { threshold: 1000000, suffix: 'M', divisor: 1000000 },
    { threshold: 1000, suffix: 'K', divisor: 1000 }
  ]
  
  const formatter = formatters.find(f => num >= f.threshold)
  return formatter 
    ? (num / formatter.divisor).toFixed(1) + formatter.suffix
    : num.toString()
}

// Format date for release
const formatDate = (dateString: string): string => {
  return new Date(dateString).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric'
  })
}

// Stats items for display
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
      color: 'text-red-600',
      bgColor: 'bg-red-50',
      borderColor: 'border-red-200'
    }
  ]
})

onMounted(() => {
  fetchAll()
  
  // Set up refresh interval if specified
  if (props.refreshInterval > 0) {
    const intervalId = setInterval(() => {
      fetchAll()
    }, props.refreshInterval)
    
    // Clean up interval on unmount
    onUnmounted(() => {
      clearInterval(intervalId)
    })
  }
})
</script>

<template>
  <section id="github-stats" class="py-12 sm:py-16 md:py-20 bg-gray-50">
    <div class="max-w-7xl mx-auto px-3 sm:px-6 lg:px-8">
      <!-- Section header -->
      <div class="text-center mb-10 sm:mb-12 md:mb-16">
        <h2 class="text-2xl sm:text-3xl md:text-4xl font-bold text-gray-900 mb-3 sm:mb-4 px-2">
          {{ t('github.title') }}
        </h2>
        <p class="text-lg sm:text-xl text-gray-600 max-w-3xl mx-auto px-4">
          {{ t('github.subtitle') }}
        </p>
      </div>

      <!-- Loading state -->
      <div v-if="loading && !stats" class="text-center">
        <div class="inline-flex items-center px-6 py-3 bg-white rounded-lg shadow-md">
          <svg class="animate-spin -ml-1 mr-3 h-5 w-5 text-blue-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
          {{ t('github.loading') }}
        </div>
      </div>

      <!-- Error state -->
      <div v-else-if="error" class="text-center">
        <div class="inline-flex items-center px-6 py-3 bg-red-50 text-red-700 rounded-lg border border-red-200">
          <svg class="w-5 h-5 mr-2" fill="currentColor" viewBox="0 0 20 20">
            <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clip-rule="evenodd" />
          </svg>
          {{ t('github.error') }}: {{ error }}
        </div>
      </div>

      <!-- Stats display -->
      <div v-else-if="stats" class="space-y-12">
        <!-- Main stats grid -->
        <div class="grid grid-cols-1 sm:grid-cols-3 gap-4 sm:gap-6">
          <div 
            v-for="item in statsItems" 
            :key="item.id"
            :class="`group ${item.bgColor} ${item.borderColor} border-2 rounded-lg sm:rounded-xl p-4 sm:p-6 text-center hover:shadow-lg transition-all duration-300 transform active:scale-95 sm:hover:-translate-y-1 touch-manipulation cursor-pointer relative overflow-hidden`"
          >
            <div class="text-3xl sm:text-4xl mb-2 sm:mb-3 transition-transform duration-300 group-hover:scale-125 group-hover:rotate-12">{{ item.icon }}</div>
            <div :class="`text-2xl sm:text-3xl font-bold ${item.color} mb-1 sm:mb-2 transition-all duration-300 group-hover:scale-110`">
              {{ item.value }}
            </div>
            <div class="text-sm sm:text-base text-gray-600 font-medium transition-colors duration-300 group-hover:text-gray-800">
              {{ item.label }}
            </div>
            <!-- Shimmer effect -->
            <div class="absolute inset-0 bg-gradient-to-r from-transparent via-white/30 to-transparent -translate-x-full group-hover:translate-x-full transition-transform duration-700"></div>
          </div>
        </div>

        <!-- Additional info -->
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4 sm:gap-6">
          <!-- Repository info -->
          <div class="group bg-white rounded-lg sm:rounded-xl p-4 sm:p-6 shadow-md border border-gray-200 hover:shadow-lg hover:border-blue-200 transition-all duration-300 cursor-pointer">
            <h3 class="text-lg sm:text-xl font-semibold text-gray-900 mb-3 sm:mb-4 flex items-center group-hover:text-blue-600 transition-colors duration-300">
              <svg class="w-5 h-5 sm:w-6 sm:h-6 mr-2 transition-transform duration-300 group-hover:rotate-12" fill="currentColor" viewBox="0 0 20 20">
                <path fill-rule="evenodd" d="M3 4a1 1 0 011-1h12a1 1 0 011 1v2a1 1 0 01-1 1H4a1 1 0 01-1-1V4zm0 4a1 1 0 011-1h12a1 1 0 011 1v6a1 1 0 01-1 1H4a1 1 0 01-1-1V8z" clip-rule="evenodd" />
              </svg>
              {{ t('github.repository') }}
            </h3>
            <p class="text-sm sm:text-base text-gray-600 mb-3 sm:mb-4 leading-relaxed">{{ repoData?.description }}</p>
            <div class="flex flex-wrap gap-2">
              <span v-if="showLanguage && repoData?.language" class="inline-flex items-center px-2 sm:px-3 py-1 rounded-full text-xs sm:text-sm font-medium bg-blue-100 text-blue-800">
                {{ repoData.language }}
              </span>
              <span class="inline-flex items-center px-2 sm:px-3 py-1 rounded-full text-xs sm:text-sm font-medium bg-green-100 text-green-800">
                {{ t('github.openSource') }}
              </span>
            </div>
          </div>

          <!-- Latest release -->
          <div v-if="showRelease" class="group bg-white rounded-lg sm:rounded-xl p-4 sm:p-6 shadow-md border border-gray-200 hover:shadow-lg hover:border-purple-200 transition-all duration-300 cursor-pointer">
            <h3 class="text-lg sm:text-xl font-semibold text-gray-900 mb-3 sm:mb-4 flex items-center group-hover:text-purple-600 transition-colors duration-300">
              <svg class="w-5 h-5 sm:w-6 sm:h-6 mr-2 transition-transform duration-300 group-hover:rotate-12" fill="currentColor" viewBox="0 0 20 20">
                <path fill-rule="evenodd" d="M5 2a1 1 0 011 1v1h1a1 1 0 010 2H6v1a1 1 0 01-2 0V6H3a1 1 0 010-2h1V3a1 1 0 011-1zm0 10a1 1 0 011 1v1h1a1 1 0 110 2H6v1a1 1 0 11-2 0v-1H3a1 1 0 110-2h1v-1a1 1 0 011-1zM12 2a1 1 0 01.967.744L14.146 7.2 17.5 9.134a1 1 0 010 1.732L14.146 12.8l-1.179 4.456a1 1 0 01-1.934 0L9.854 12.8 6.5 10.866a1 1 0 010-1.732L9.854 7.2l1.179-4.456A1 1 0 0112 2z" clip-rule="evenodd" />
              </svg>
              {{ t('github.latestRelease') }}
            </h3>
            <div v-if="latestRelease">
              <div class="text-xl sm:text-2xl font-bold text-blue-600 mb-2">
                {{ latestRelease.tag_name }}
              </div>
              <div class="text-gray-600 text-xs sm:text-sm">
                {{ t('github.released') }} {{ formatDate(latestRelease.published_at) }}
              </div>
              <a 
                :href="latestRelease.html_url" 
                target="_blank" 
                rel="noopener noreferrer"
                class="inline-flex items-center mt-3 text-sm sm:text-base text-blue-600 hover:text-blue-800 font-medium touch-manipulation"
              >
                {{ t('github.viewRelease') }}
                <svg class="w-3 h-3 sm:w-4 sm:h-4 ml-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                </svg>
              </a>
            </div>
            <div v-else class="text-sm sm:text-base text-gray-500">
              {{ t('github.noReleases') }}
            </div>
          </div>
        </div>

        <!-- Call to action -->
        <div class="text-center px-4">
          <a 
            :href="repoData?.html_url" 
            target="_blank" 
            rel="noopener noreferrer"
            class="inline-flex items-center px-6 sm:px-8 py-3 sm:py-4 bg-gray-900 text-white font-semibold rounded-lg hover:bg-gray-800 active:bg-black transition-all duration-200 transform active:scale-95 sm:hover:scale-105 shadow-lg hover:shadow-xl touch-manipulation"
          >
            <svg class="w-5 h-5 sm:w-6 sm:h-6 mr-2 sm:mr-3" fill="currentColor" viewBox="0 0 20 20">
              <path fill-rule="evenodd" d="M10 0C4.477 0 0 4.484 0 10.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0110 4.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.203 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.942.359.31.678.921.678 1.856 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0020 10.017C20 4.484 15.522 0 10 0z" clip-rule="evenodd" />
            </svg>
            <span class="text-sm sm:text-base">{{ t('github.viewOnGitHub') }}</span>
          </a>
        </div>
      </div>
    </div>
  </section>
</template>