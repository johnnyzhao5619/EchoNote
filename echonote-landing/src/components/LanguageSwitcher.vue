<template>
  <div class="inline-flex items-center">
    <label class="sr-only" for="locale-switcher">{{ t('header.languageSwitcher') }}</label>
    <select
      id="locale-switcher"
      v-model="currentLocale"
      class="h-10 min-w-[7.5rem] rounded-lg border border-slate-200 bg-white px-3 text-sm font-medium text-slate-700 outline-none transition-colors hover:border-slate-300 focus:border-slate-400 focus:ring-2 focus:ring-slate-200"
      :aria-label="t('header.languageSwitcher')"
    >
      <option v-for="localeConfig in supportedLocales" :key="localeConfig.code" :value="localeConfig.code">
        {{ localeConfig.name }}
      </option>
    </select>
  </div>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { computed } from 'vue'
import { SUPPORTED_LOCALES } from '../i18n/locales'

const { locale, t } = useI18n()

const supportedLocales = SUPPORTED_LOCALES
const currentLocale = computed({
  get: () => locale.value,
  set: (lang: string) => {
    locale.value = lang
  },
})
</script>
