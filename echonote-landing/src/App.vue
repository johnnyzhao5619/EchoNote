<script setup lang="ts">
import { projectConfig } from './config/project'
import Header from './components/Header.vue'
import Footer from './components/Footer.vue'
import Hero from './components/Hero.vue'
import Features from './components/Features.vue'
import HowItWorks from './components/HowItWorks.vue'
import GitHubStats from './components/GitHubStats.vue'
</script>

<template>
  <div class="min-h-screen flex flex-col">
    <Header />

    <main id="main-content" class="flex-1">
      <Hero />

      <Features :features="projectConfig.features" />

      <HowItWorks />
      <GitHubStats />
    </main>

    <Footer />
  </div>
</template>
