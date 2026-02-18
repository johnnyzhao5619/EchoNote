import { ref, computed, readonly } from 'vue'
import type { GitHubRepository, GitHubRelease, GitHubStats, GitHubApiError } from '../types/github'
import { githubConfig } from '../config/project'

export function useGitHubApi(owner: string, repo: string) {
  const apiBase = githubConfig.apiUrl.replace(/\/+$/, '')
  const repoEndpoint = `${apiBase}/repos/${owner}/${repo}`

  const repository = ref<GitHubRepository | null>(null)
  const latestRelease = ref<GitHubRelease | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  const stats = computed<GitHubStats | null>(() => {
    if (!repository.value) return null

    return {
      stars: repository.value.stargazers_count,
      forks: repository.value.forks_count,
      issues: repository.value.open_issues_count,
      latestRelease: latestRelease.value?.tag_name,
      language: repository.value.language,
    }
  })

  const fetchRepository = async (): Promise<void> => {
    try {
      loading.value = true
      error.value = null

      const response = await fetch(repoEndpoint)

      if (!response.ok) {
        const errorData: GitHubApiError = await response.json()
        throw new Error(errorData.message || `HTTP ${response.status}`)
      }

      repository.value = await response.json()
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to fetch repository data'
      console.error('GitHub API Error:', err)
    } finally {
      loading.value = false
    }
  }

  const fetchLatestRelease = async (): Promise<void> => {
    try {
      const response = await fetch(`${repoEndpoint}/releases/latest`)

      if (response.ok) {
        latestRelease.value = await response.json()
      }
      // Don't throw error if no releases exist
    } catch (err) {
      console.warn('Could not fetch latest release:', err)
    }
  }

  const fetchAll = async (): Promise<void> => {
    await Promise.all([fetchRepository(), fetchLatestRelease()])
  }

  const refresh = async (): Promise<void> => {
    await fetchAll()
  }

  return {
    repository: readonly(repository),
    latestRelease: readonly(latestRelease),
    stats: readonly(stats),
    loading: readonly(loading),
    error: readonly(error),
    fetchRepository,
    fetchLatestRelease,
    fetchAll,
    refresh,
  }
}
