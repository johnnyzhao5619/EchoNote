<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { projectConfig } from '../config/project'
import Hero from '../components/Hero.vue'
import Features from '../components/Features.vue'
import GitHubStats from '../components/GitHubStats.vue'
import HowItWorks from '../components/HowItWorks.vue'

const { t } = useI18n()

// Configure hero section with secondary action
const heroSecondaryAction = {
  text: 'hero.learnMore',
  url: '#features',
  type: 'secondary' as const,
  external: false
}
</script>

<template>
  <main id="main-content" class="flex-1 bg-slate-50">
    <Hero
      :title="t('hero.headline')"
      :description="t('hero.description')"
      :secondary-action="heroSecondaryAction"
    />

    <Features
      :features="projectConfig.features"
      :title="t('features.title')"
      :subtitle="t('features.subtitle')"
    />

    <HowItWorks />

    <GitHubStats />
  </main>
</template>
