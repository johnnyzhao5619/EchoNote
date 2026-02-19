import './assets/main.css'

import { createApp, watch } from 'vue'
import App from './App.vue'
import i18n from './i18n'
import { LOCALE_STORAGE_KEY } from './i18n/locales'

const app = createApp(App)

app.use(i18n)

const syncLocaleToDocument = (locale: string) => {
  if (typeof document !== 'undefined') {
    document.documentElement.setAttribute('lang', locale)
  }
  if (typeof window !== 'undefined') {
    window.localStorage.setItem(LOCALE_STORAGE_KEY, locale)
  }
}

syncLocaleToDocument(i18n.global.locale.value)
watch(() => i18n.global.locale.value, syncLocaleToDocument)

app.mount('#app')
