<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { projectConfig } from '../config/project'
import { useResponsiveImage } from '../composables/useLogo'
import bannerUrl from '@/assets/Banner.svg'
import type { ActionButton } from '../types'

const { t } = useI18n()

// Banner image handling
const { 
  imageSrc: bannerSrc, 
  isLoading: bannerLoading, 
  hasError: bannerError, 
  imageAlt: bannerAlt,
  handleImageError: handleBannerError,
  handleImageLoad: handleBannerLoad
} = useResponsiveImage(bannerUrl, 'EchoNote application interface preview')

interface Props {
  title?: string
  description?: string
  primaryAction?: ActionButton
  secondaryAction?: ActionButton
  backgroundImage?: string
}

withDefaults(defineProps<Props>(), {
  title: () => projectConfig.name,
  description: () => projectConfig.description,
  primaryAction: () => ({
    text: 'hero.viewOnGitHub',
    url: projectConfig.githubUrl,
    type: 'primary' as const,
    external: true
  })
})

const scrollToFeatures = (e: Event) => {
  e.preventDefault()
  const el = document.getElementById('features')
  if (el) {
    el.scrollIntoView({ behavior: 'smooth' })
  }
}

const releaseBadge = computed(() =>
  t('hero.releaseBadge', { version: projectConfig.releaseTag || 'latest' }),
)

const quickLinks = computed(() => {
  const items = [
    { label: t('hero.quickLinks.documentation'), href: projectConfig.links.documentation },
    { label: t('hero.quickLinks.issues'), href: projectConfig.links.issues },
    { label: t('hero.quickLinks.releases'), href: projectConfig.links.download },
    { label: t('hero.quickLinks.license'), href: projectConfig.links.license },
  ]
  return items.filter((item): item is { label: string; href: string } => Boolean(item.href))
})
</script>

<template>
  <section
    class="section-shell relative overflow-hidden bg-slate-50"
    :style="backgroundImage ? `background-image: url(${backgroundImage})` : ''"
  >
    <div class="absolute inset-0 bg-slate-50">
      <div class="absolute right-[-5%] top-[-10%] h-[500px] w-[500px] animate-float rounded-full bg-sky-200/40 blur-[100px]"></div>
      <div class="absolute bottom-[-10%] left-[-10%] w-[600px] h-[600px] bg-blue-200/40 rounded-full blur-[100px] animate-float animation-delay-200"></div>
      <div class="absolute top-[20%] left-[20%] w-[300px] h-[300px] bg-indigo-200/40 rounded-full blur-[80px] animate-float animation-delay-600"></div>
    </div>

    <div class="site-container relative z-10">
      <div class="grid items-center gap-12 lg:grid-cols-[1.05fr_0.95fr]">
        <div class="text-center lg:text-left">
          <div class="mb-6 inline-flex items-center gap-2 rounded-full border border-blue-100 bg-blue-50 px-3 py-1 text-sm font-medium text-blue-700 animate-fade-in-up">
            <span class="relative flex h-2 w-2">
              <span class="absolute inline-flex h-full w-full animate-ping rounded-full bg-blue-400 opacity-75"></span>
              <span class="relative inline-flex h-2 w-2 rounded-full bg-blue-500"></span>
            </span>
            {{ releaseBadge }}
          </div>

          <h1 class="mb-6 text-4xl font-bold tracking-tight text-slate-900 animate-fade-in-up animation-delay-100 sm:text-5xl md:text-6xl">
            {{ title }}
          </h1>

          <p class="mx-auto mb-10 max-w-2xl text-lg leading-relaxed text-slate-600 animate-fade-in-up animation-delay-200 lg:mx-0">
            {{ description }}
          </p>

          <div class="mb-8 flex w-full flex-col gap-4 animate-fade-in-up animation-delay-300 sm:w-auto sm:flex-row lg:justify-start">
            <a
              v-if="primaryAction"
              :href="primaryAction.url"
              :target="primaryAction.external ? '_blank' : '_self'"
              rel="noopener noreferrer"
              class="group relative inline-flex items-center justify-center overflow-hidden rounded-full bg-slate-900 px-8 py-3.5 text-base font-semibold text-white transition-all duration-200 hover:-translate-y-1 hover:bg-slate-800 hover:shadow-lg focus:outline-none focus:ring-2 focus:ring-slate-900 focus:ring-offset-2"
            >
              <div class="absolute inset-0 h-full w-full bg-gradient-to-r from-blue-600 to-indigo-600 opacity-0 transition-opacity duration-300 group-hover:opacity-100"></div>
              <span class="relative flex items-center gap-2">
                <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 24 24" aria-hidden="true"><path fill-rule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0110 4.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.203 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.942.359.31.678.921.678 1.856 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0020 10.017C20 4.484 15.522 0 10 0z" clip-rule="evenodd"></path></svg>
                {{ t(primaryAction.text) }}
              </span>
            </a>

            <a
              v-if="secondaryAction"
              :href="secondaryAction.url"
              @click="secondaryAction.url === '#features' ? scrollToFeatures($event) : null"
              class="group inline-flex items-center justify-center rounded-full border border-slate-200 bg-white px-8 py-3.5 text-base font-semibold text-slate-700 transition-all duration-200 hover:border-slate-300 hover:bg-slate-50 hover:text-slate-900 hover:shadow-md focus:outline-none focus:ring-2 focus:ring-slate-200 focus:ring-offset-2"
            >
              {{ t(secondaryAction.text) }}
            </a>
          </div>

          <div class="flex flex-wrap items-center justify-center gap-2 text-sm text-slate-600 lg:justify-start">
            <a
              v-for="link in quickLinks"
              :key="link.href"
              :href="link.href"
              target="_blank"
              rel="noopener noreferrer"
              class="rounded-full border border-slate-200 bg-white px-3 py-1.5 font-medium transition-colors hover:border-slate-300 hover:bg-slate-100 hover:text-slate-900"
            >
              {{ link.label }}
            </a>
          </div>
        </div>

        <div class="relative w-full max-w-4xl animate-fade-in-up animation-delay-600 lg:ml-auto">
          <div class="relative rounded-xl bg-slate-900 p-2 shadow-2xl ring-1 ring-slate-900/10">
            <div class="absolute left-0 right-0 top-0 flex h-8 items-center space-x-2 rounded-t-lg bg-slate-800 px-4">
              <div class="h-3 w-3 rounded-full bg-red-500"></div>
              <div class="h-3 w-3 rounded-full bg-yellow-500"></div>
              <div class="h-3 w-3 rounded-full bg-green-500"></div>
            </div>

            <div class="mt-6 aspect-[16/10] overflow-hidden rounded-lg bg-slate-800">
              <img
                :src="bannerSrc"
                :alt="bannerAlt"
                class="h-full w-full object-cover"
                :class="{ 'opacity-50': bannerLoading }"
                @error="handleBannerError"
                @load="handleBannerLoad"
              />
              <div
                v-if="bannerLoading && !bannerError"
                class="absolute inset-0 flex items-center justify-center"
              >
                <div class="h-12 w-12 animate-spin rounded-full border-4 border-slate-600 border-t-white"></div>
              </div>
            </div>

            <div class="pointer-events-none absolute inset-0 rounded-xl bg-gradient-to-tr from-white/5 to-transparent"></div>
          </div>

          <div class="absolute -inset-4 -z-10 rounded-xl bg-gradient-to-r from-blue-500 to-indigo-500 opacity-20 blur-2xl transition-opacity duration-500"></div>
        </div>
      </div>
    </div>
  </section>
</template>
