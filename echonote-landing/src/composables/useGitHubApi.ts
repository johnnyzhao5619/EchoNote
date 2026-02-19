import { computed, readonly, ref } from 'vue'
import { githubConfig } from '../config/project'
import type { GitHubApiError, GitHubRelease, GitHubRepository, GitHubStats } from '../types/github'

const CACHE_TTL_MS = 5 * 60 * 1000

interface GitHubCacheEntry {
  repository: GitHubRepository
  latestRelease: GitHubRelease | null
  fetchedAt: number
}

export function useGitHubApi(owner: string, repo: string) {
  const apiBase = githubConfig.apiUrl.replace(/\/+$/, '')
  const repoEndpoint = `${apiBase}/repos/${owner}/${repo}`
  const cacheKey = `echonote-landing:github:${owner}/${repo}`

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

  const loadCache = (): boolean => {
    if (typeof window === 'undefined') return false

    try {
      const rawValue = window.sessionStorage.getItem(cacheKey)
      if (!rawValue) return false

      const parsed: GitHubCacheEntry = JSON.parse(rawValue)
      const isExpired = Date.now() - parsed.fetchedAt > CACHE_TTL_MS
      if (isExpired) return false

      repository.value = parsed.repository
      latestRelease.value = parsed.latestRelease
      return true
    } catch {
      return false
    }
  }

  const saveCache = () => {
    if (typeof window === 'undefined' || !repository.value) return

    const payload: GitHubCacheEntry = {
      repository: repository.value,
      latestRelease: latestRelease.value,
      fetchedAt: Date.now(),
    }

    try {
      window.sessionStorage.setItem(cacheKey, JSON.stringify(payload))
    } catch {
      // Ignore cache write failures.
    }
  }

  const fetchRepository = async (): Promise<void> => {
    const response = await fetch(repoEndpoint)

    if (!response.ok) {
      let apiError: GitHubApiError | null = null
      try {
        apiError = (await response.json()) as GitHubApiError
      } catch {
        apiError = null
      }
      throw new Error(apiError?.message || `HTTP ${response.status}`)
    }

    repository.value = (await response.json()) as GitHubRepository
  }

  const fetchLatestRelease = async (): Promise<void> => {
    try {
      const response = await fetch(`${repoEndpoint}/releases/latest`)
      if (response.ok) {
        latestRelease.value = (await response.json()) as GitHubRelease
      }
    } catch {
      // Ignore release fetch errors to keep repository metrics available.
    }
  }

  const fetchAll = async (forceRefresh = false): Promise<void> => {
    if (!forceRefresh && loadCache()) {
      error.value = null
      return
    }

    loading.value = true
    error.value = null

    try {
      await Promise.all([fetchRepository(), fetchLatestRelease()])
      saveCache()
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to fetch repository data'
    } finally {
      loading.value = false
    }
  }

  const refresh = async (): Promise<void> => {
    await fetchAll(true)
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
