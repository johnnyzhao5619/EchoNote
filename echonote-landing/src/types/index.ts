// Core application types and interfaces

export interface Feature {
  id: string
  icon: string
  title: string
  description: string
}

export interface ProjectLinks {
  documentation?: string
  demo?: string
  download?: string
  issues?: string
  discussions?: string
  contributing?: string
  license?: string
}

export interface SEOConfig {
  title: string
  description: string
  keywords: string[]
  ogImage?: string
  ogUrl?: string
}

export interface HowItWorksStep {
  step: number
  title: string
  description: string
  icon: string
}

export interface ProjectConfig {
  name: string
  description: string
  githubUrl: string
  features: Feature[]
  howItWorks?: HowItWorksStep[]
  links: ProjectLinks
  seo: SEOConfig
}
