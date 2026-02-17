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
export const LOCALE_STORAGE_KEY = 'echonote-landing-locale'

const SUPPORTED_LOCALE_CODES = new Set(SUPPORTED_LOCALES.map((locale) => locale.code))

export const isSupportedLocale = (locale: string): boolean => SUPPORTED_LOCALE_CODES.has(locale)

export const resolveInitialLocale = (): string => {
  if (typeof window === 'undefined') {
    return DEFAULT_LOCALE
  }

  const storedLocale = window.localStorage.getItem(LOCALE_STORAGE_KEY)
  if (storedLocale && isSupportedLocale(storedLocale)) {
    return storedLocale
  }

  const browserLocale = window.navigator.language
  if (isSupportedLocale(browserLocale)) {
    return browserLocale
  }

  const languageOnlyMatch = SUPPORTED_LOCALES.find((locale) =>
    locale.code.split('-')[0] === browserLocale.split('-')[0],
  )
  return languageOnlyMatch?.code || DEFAULT_LOCALE
}
