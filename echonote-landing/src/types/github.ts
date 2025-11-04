// GitHub API related types

export interface GitHubRepository {
  name: string
  description: string
  stargazers_count: number
  forks_count: number
  open_issues_count: number
  html_url: string
  homepage?: string
  license?: {
    name: string
    spdx_id: string
  }
  created_at: string
  updated_at: string
  language?: string
  topics?: string[]
}

export interface GitHubRelease {
  tag_name: string
  name: string
  published_at: string
  html_url: string
  body?: string
  prerelease: boolean
  draft: boolean
}

export interface GitHubStats {
  stars: number
  forks: number
  issues: number
  latestRelease?: string
  contributors: number
  language?: string
}

export interface GitHubApiError {
  message: string
  status: number
  documentation_url?: string
}
