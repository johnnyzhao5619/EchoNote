<script setup lang="ts">
import { projectConfig } from './config/project'
import Header from './components/Header.vue'
import Footer from './components/Footer.vue'
import Hero from './components/Hero.vue'
import ValueProps from './components/ValueProps.vue'
import Features from './components/Features.vue'
import HowItWorks from './components/HowItWorks.vue'
import GitHubStats from './components/GitHubStats.vue'
import FAQ from './components/FAQ.vue'
</script>

<template>
  <div
    class="min-h-screen flex flex-col bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100 transition-colors duration-300"
  >
    <Header />

    <main id="main-content" class="flex-1">
      <Hero />
      <ValueProps />
      <Features :features="projectConfig.features" />

      <HowItWorks :steps="projectConfig.howItWorks || []" />
      <GitHubStats />
      <FAQ />
    </main>

    <Footer />
  </div>
</template>
