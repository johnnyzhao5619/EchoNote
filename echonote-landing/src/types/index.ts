// Core application types and interfaces

export interface ActionButton {
  text: string
  url: string
  type: 'primary' | 'secondary'
  external?: boolean
}

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
}

export interface SEOConfig {
  title: string
  description: string
  keywords: string[]
  ogImage?: string
  ogUrl?: string
}

export interface ProjectConfig {
  name: string
  description: string
  githubUrl: string
  features: Feature[]
  links: ProjectLinks
  seo: SEOConfig
}
