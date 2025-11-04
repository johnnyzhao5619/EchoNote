// Component prop types and interfaces

import type { ActionButton, Feature } from './index'

export interface HeaderProps {
  githubUrl: string
  showLanguageSwitch?: boolean
  projectName?: string
}

export interface HeroProps {
  title: string
  description: string
  primaryAction: ActionButton
  secondaryAction?: ActionButton
  backgroundImage?: string
}

export interface FeaturesProps {
  features: Feature[]
  columns?: number
  title?: string
}

export interface GitHubStatsProps {
  repository: string
  refreshInterval?: number
  showContributors?: boolean
}

export interface FooterProps {
  projectName: string
  githubUrl: string
  license?: string
  year?: number
}

// Language switcher types
export interface LanguageOption {
  code: string
  name: string
  flag?: string
}

export interface LanguageSwitcherProps {
  options: LanguageOption[]
  currentLanguage: string
  onLanguageChange: (language: string) => void
}
