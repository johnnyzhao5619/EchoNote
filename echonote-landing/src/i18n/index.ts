import { createI18n } from 'vue-i18n'
import { DEFAULT_LOCALE, FALLBACK_LOCALE } from './locales'
import zhCN from '../locales/zh-CN.json'
import zhTW from '../locales/zh-TW.json'
import enUS from '../locales/en-US.json'
import frFR from '../locales/fr-FR.json'

const messages = {
  'zh-CN': zhCN,
  'zh-TW': zhTW,
  'en-US': enUS,
  'fr-FR': frFR,
}

const i18n = createI18n({
  legacy: false,
  locale: DEFAULT_LOCALE,
  fallbackLocale: FALLBACK_LOCALE,
  messages,
})

export default i18n
