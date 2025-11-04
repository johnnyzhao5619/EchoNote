<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { projectConfig } from '../config/project'
import Hero from '../components/Hero.vue'
import Features from '../components/Features.vue'
import GitHubStats from '../components/GitHubStats.vue'

const { t } = useI18n()

// Configure hero section with secondary action
const heroSecondaryAction = {
  text: 'hero.learnMore',
  url: projectConfig.links.documentation || '#features',
  type: 'secondary' as const,
  external: false
}
</script>

<template>
  <main class="flex-1">
    <!-- Hero Section -->
    <Hero 
      :title="t('hero.title')"
      :description="t('hero.description')"
      :secondary-action="heroSecondaryAction"
    />

    <!-- Features Section -->
    <Features 
      :features="projectConfig.features"
      :title="t('features.title')"
      :subtitle="t('features.subtitle')"
    />

    <!-- GitHub Stats Section -->
    <GitHubStats />
  </main>
</template>