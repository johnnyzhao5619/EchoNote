import type { ProjectConfig } from '../types'

// Base configuration - centralized to avoid hardcoding
const GITHUB_OWNER = 'johnnyzhao5619'
const GITHUB_REPO = 'EchoNote'
const PROJECT_NAME = 'EchoNote'
const BASE_URL = `https://${GITHUB_OWNER}.github.io/${GITHUB_REPO}`
const GITHUB_URL = `https://github.com/${GITHUB_OWNER}/${GITHUB_REPO}`
const DOCS_URL = `${GITHUB_URL}/tree/main/docs`

export const projectConfig: ProjectConfig & any = {
  name: PROJECT_NAME,
  description:
    'A local-first desktop application for comprehensive note management, voice transcription, and AI-powered note summarization.',
  githubUrl: GITHUB_URL,

  valueProps: [
    {
      id: 'local',
      title: 'valueProps.local.title',
      description: 'valueProps.local.description',
    },
    {
      id: 'private',
      title: 'valueProps.private.title',
      description: 'valueProps.private.description',
    },
    {
      id: 'powerful',
      title: 'valueProps.powerful.title',
      description: 'valueProps.powerful.description',
    },
  ],

  features: [
    {
      id: 'note-management',
      icon: '🗂️',
      title: 'features.items.noteManagement.title',
      description: 'features.items.noteManagement.description',
    },
    {
      id: 'ai-summarization',
      icon: '🧠',
      title: 'features.items.aiSummarization.title',
      description: 'features.items.aiSummarization.description',
    },
    {
      id: 'realtime-recording',
      icon: '⏱️',
      title: 'features.items.realtimeRecording.title',
      description: 'features.items.realtimeRecording.description',
    },
    {
      id: 'batch-transcription',
      icon: '🎙️',
      title: 'features.items.batchTranscription.title',
      description: 'features.items.batchTranscription.description',
    },
    {
      id: 'privacy-first',
      icon: '🔒',
      title: 'features.items.privacyFirst.title',
      description: 'features.items.privacyFirst.description',
    },
    {
      id: 'multilingual',
      icon: '🌍',
      title: 'features.items.multilingualWorkflow.title',
      description: 'features.items.multilingualWorkflow.description',
    },
  ],

  faqs: [
    {
      id: 'q1',
      question: 'faq.q1.question',
      answer: 'faq.q1.answer',
    },
    {
      id: 'q2',
      question: 'faq.q2.question',
      answer: 'faq.q2.answer',
    },
    {
      id: 'q3',
      question: 'faq.q3.question',
      answer: 'faq.q3.answer',
    },
    {
      id: 'q4',
      question: 'faq.q4.question',
      answer: 'faq.q4.answer',
    },
  ],

  howItWorks: [
    {
      step: 1,
      title: 'howItWorks.steps.capture.title',
      description: 'howItWorks.steps.capture.description',
      icon: 'mic',
    },
    {
      step: 2,
      title: 'howItWorks.steps.transcribe.title',
      description: 'howItWorks.steps.transcribe.description',
      icon: 'cpu',
    },
    {
      step: 3,
      title: 'howItWorks.steps.organize.title',
      description: 'howItWorks.steps.organize.description',
      icon: 'search',
    },
  ],

  links: {
    documentation: DOCS_URL,
    demo: `${BASE_URL}/demo`,
    download: `${GITHUB_URL}/releases/latest`,
    issues: `${GITHUB_URL}/issues`,
    discussions: `${GITHUB_URL}/discussions`,
    contributing: `${GITHUB_URL}/blob/main/docs/CONTRIBUTING.md`,
    license: `${GITHUB_URL}/blob/main/LICENSE`,
  },

  seo: {
    title: `${PROJECT_NAME} - Local-First Voice Transcription & Calendar Workflow`,
    description: `${PROJECT_NAME} is an open-source desktop app for comprehensive note management, voice transcription, and AI note summarization.`,
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
  '@graph': [
    {
      '@type': 'SoftwareApplication',
      '@id': `${BASE_URL}/#application`,
      name: PROJECT_NAME,
      description: projectConfig.description,
      url: BASE_URL,
      applicationCategory: 'ProductivityApplication',
      operatingSystem: 'Cross-platform',
      offers: {
        '@type': 'Offer',
        price: '0',
        priceCurrency: 'USD',
      },
      author: {
        '@id': `${BASE_URL}/#organization`,
      },
      license: 'https://www.apache.org/licenses/LICENSE-2.0',
    },
    {
      '@type': 'Organization',
      '@id': `${BASE_URL}/#organization`,
      name: GITHUB_OWNER,
      url: GITHUB_URL,
    },
    {
      '@type': 'WebSite',
      '@id': `${BASE_URL}/#website`,
      url: BASE_URL,
      name: PROJECT_NAME,
      description: projectConfig.description,
      publisher: {
        '@id': `${BASE_URL}/#organization`,
      },
    },
  ],
}

// License information
export const licenseInfo = {
  name: 'Apache License 2.0',
  url: 'https://www.apache.org/licenses/LICENSE-2.0',
}
