export interface LocaleConfig {
  code: string
  name: string
  flag?: string
}

export const SUPPORTED_LOCALES: LocaleConfig[] = [
  { code: 'zh-CN', name: '简体中文' },
  { code: 'zh-TW', name: '繁體中文' },
  { code: 'en-US', name: 'English' },
  { code: 'fr-FR', name: 'Français' },
]

export const DEFAULT_LOCALE = 'zh-CN'
export const FALLBACK_LOCALE = 'en-US'
