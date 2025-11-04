<template>
  <div class="language-switcher">
    <button 
      v-for="localeConfig in supportedLocales"
      :key="localeConfig.code"
      @click="switchLanguage(localeConfig.code)"
      :class="{ 'active': currentLocale === localeConfig.code }"
      class="px-3 py-1 mx-1 rounded border transition-colors"
    >
      {{ localeConfig.name }}
    </button>
  </div>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { computed } from 'vue'
import { SUPPORTED_LOCALES } from '../i18n/locales'

const { locale } = useI18n()

const supportedLocales = SUPPORTED_LOCALES
const currentLocale = computed(() => locale.value)

const switchLanguage = (lang: string) => {
  locale.value = lang
}
</script>

<style scoped>
.active {
  background-color: #3b82f6;
  color: white;
}
</style>