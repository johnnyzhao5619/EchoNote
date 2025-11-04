import type { ProjectConfig } from '../types'

// Base configuration - centralized to avoid hardcoding
const GITHUB_OWNER = 'johnnyzhao5619'
const GITHUB_REPO = 'EchoNote'
const PROJECT_NAME = 'EchoNote'
const BASE_URL = `https://${GITHUB_OWNER}.github.io/${GITHUB_REPO}`
const GITHUB_URL = `https://github.com/${GITHUB_OWNER}/${GITHUB_REPO}`

export const projectConfig: ProjectConfig = {
  name: PROJECT_NAME,
  description:
    'A modern, open-source note-taking application with powerful features for organizing and managing your thoughts.',
  githubUrl: GITHUB_URL,

  features: [
    {
      id: 'markdown-support',
      icon: '📝',
      title: 'Markdown Support',
      description: 'Write notes in Markdown with live preview and syntax highlighting.',
    },
    {
      id: 'organization',
      icon: '📁',
      title: 'Smart Organization',
      description: 'Organize notes with tags, folders, and powerful search capabilities.',
    },
    {
      id: 'sync',
      icon: '☁️',
      title: 'Cloud Sync',
      description: 'Sync your notes across all devices with secure cloud storage.',
    },
    {
      id: 'collaboration',
      icon: '👥',
      title: 'Collaboration',
      description: 'Share and collaborate on notes with team members in real-time.',
    },
    {
      id: 'themes',
      icon: '🎨',
      title: 'Customizable Themes',
      description: 'Choose from multiple themes or create your own custom appearance.',
    },
    {
      id: 'export',
      icon: '📤',
      title: 'Export Options',
      description: 'Export notes to PDF, HTML, or other formats for sharing and archiving.',
    },
  ],

  links: {
    documentation: `${GITHUB_URL}/wiki`,
    demo: `${BASE_URL}/demo`,
    download: `${GITHUB_URL}/releases/latest`,
  },

  seo: {
    title: `${PROJECT_NAME} - Modern Open Source Note-Taking App`,
    description: `${PROJECT_NAME} is a powerful, open-source note-taking application with Markdown support, cloud sync, and collaboration features. Perfect for developers, writers, and teams.`,
    keywords: [
      'note-taking',
      'markdown',
      'open-source',
      'productivity',
      'collaboration',
      'cloud-sync',
      'notes-app',
      'writing',
      'documentation',
      'vue',
      'typescript',
      'github',
    ],
    ogImage: '/og-image.png',
    ogUrl: BASE_URL,
  },
}

// Language options for the language switcher
export const languageOptions = [
  {
    code: 'zh-CN',
    name: '中文',
    flag: '🇨🇳',
  },
  {
    code: 'en-US',
    name: 'English',
    flag: '🇺🇸',
  },
]

// GitHub repository configuration
export const githubConfig = {
  owner: GITHUB_OWNER,
  repo: GITHUB_REPO,
  apiUrl: 'https://api.github.com',
}

// Structured data for search engines
export const structuredData = {
  '@context': 'https://schema.org',
  '@type': 'SoftwareApplication',
  name: PROJECT_NAME,
  description: projectConfig.description,
  url: GITHUB_URL,
  applicationCategory: 'ProductivityApplication',
  operatingSystem: 'Cross-platform',
  offers: {
    '@type': 'Offer',
    price: '0',
    priceCurrency: 'USD',
  },
  author: {
    '@type': 'Person',
    name: GITHUB_OWNER,
  },
  license: 'https://opensource.org/licenses/MIT',
}

// Technology stack information
export const techStack = ['Vue 3', 'TypeScript', 'Tailwind CSS']

// License information
export const licenseInfo = {
  name: 'MIT License',
  url: 'https://opensource.org/licenses/MIT',
}

// Additional meta tags for better SEO
export const additionalMetaTags = [
  { name: 'author', content: GITHUB_OWNER },
  { name: 'robots', content: 'index, follow' },
  { name: 'language', content: 'en, zh' },
  { name: 'revisit-after', content: '7 days' },
  { name: 'theme-color', content: '#3b82f6' },
  { property: 'og:type', content: 'website' },
  { property: 'og:site_name', content: PROJECT_NAME },
  { name: 'twitter:card', content: 'summary_large_image' },
  { name: 'twitter:site', content: `@${PROJECT_NAME.toLowerCase()}` },
  { name: 'twitter:creator', content: `@${GITHUB_OWNER}` },
]
