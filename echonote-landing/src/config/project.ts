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
    'A local-first desktop application for voice transcription, real-time recording, and calendar-aware timeline management.',
  githubUrl: GITHUB_URL,

  features: [
    {
      id: 'batch-transcription',
      icon: '🎙️',
      title: 'Batch Transcription',
      description: 'Transcribe audio and video files with local models and export to multiple formats.',
    },
    {
      id: 'realtime-recording',
      icon: '⏱️',
      title: 'Real-time Recording',
      description: 'Capture microphone audio, annotate key moments, and generate live transcripts.',
    },
    {
      id: 'calendar-sync',
      icon: '📅',
      title: 'Calendar Integration',
      description: 'Connect Google or Outlook calendars and keep events synced with recordings.',
    },
    {
      id: 'timeline',
      icon: '🧭',
      title: 'Timeline Intelligence',
      description: 'Correlate events, recordings, and transcripts in a single searchable timeline.',
    },
    {
      id: 'privacy-first',
      icon: '🔒',
      title: 'Privacy First',
      description: 'Keep data local with encrypted storage and no mandatory cloud dependency.',
    },
    {
      id: 'multilingual',
      icon: '🌍',
      title: 'Multilingual Workflow',
      description: 'Supports multilingual speech recognition with a translation-ready UI architecture.',
    },
  ],

  links: {
    documentation: `${GITHUB_URL}/wiki`,
    demo: `${BASE_URL}/demo`,
    download: `${GITHUB_URL}/releases/latest`,
  },

  seo: {
    title: `${PROJECT_NAME} - Local-First Voice Transcription & Calendar Workflow`,
    description: `${PROJECT_NAME} is an open-source desktop app for batch transcription, real-time recording, and calendar-aware timeline management.`,
    keywords: [
      'voice transcription',
      'speech to text',
      'desktop app',
      'calendar integration',
      'timeline',
      'local first',
      'open-source',
      'privacy',
      'faster-whisper',
    ],
    ogImage: '/og-image.png',
    ogUrl: BASE_URL,
  },
}

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
  license: 'https://www.apache.org/licenses/LICENSE-2.0',
}

// Technology stack information
export const techStack = ['Vue 3', 'TypeScript', 'Tailwind CSS']

// License information
export const licenseInfo = {
  name: 'Apache License 2.0',
  url: 'https://www.apache.org/licenses/LICENSE-2.0',
}
