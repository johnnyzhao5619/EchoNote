<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { projectConfig } from '../config/project'

const { t } = useI18n()
</script>

<template>
  <section class="py-16 sm:py-24 bg-gray-50 dark:bg-gray-800/50">
    <div class="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
      <div class="mx-auto max-w-2xl lg:text-center mb-16">
        <h2
          class="text-base font-semibold leading-7 text-blue-600 dark:text-blue-400 uppercase tracking-wide"
        >
          {{ t('hero.subtitle') }}
        </h2>
        <p class="mt-2 text-3xl font-bold tracking-tight text-gray-900 dark:text-white sm:text-4xl">
          {{ t('hero.headline') }}
        </p>
      </div>

      <div class="mx-auto mt-16 max-w-2xl sm:mt-20 lg:mt-24 lg:max-w-none">
        <dl class="grid max-w-xl grid-cols-1 gap-x-8 gap-y-16 lg:max-w-none lg:grid-cols-3">
          <div
            v-for="prop in projectConfig.valueProps"
            :key="prop.id"
            class="flex flex-col items-center text-center lg:items-start lg:text-left"
          >
            <dt
              class="flex flex-col items-center lg:items-start text-xl font-semibold leading-7 text-gray-900 dark:text-white"
            >
              <div
                class="mb-6 flex h-16 w-16 items-center justify-center rounded-2xl bg-blue-600/10 dark:bg-blue-900/40"
              >
                <!-- Decorative Icon Placeholder based on id -->
                <svg
                  v-if="prop.id === 'local'"
                  class="w-8 h-8 text-blue-600 dark:text-blue-400"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 002-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"
                  />
                </svg>
                <svg
                  v-else-if="prop.id === 'private'"
                  class="w-8 h-8 text-blue-600 dark:text-blue-400"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"
                  />
                </svg>
                <svg
                  v-else
                  class="w-8 h-8 text-blue-600 dark:text-blue-400"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M13 10V3L4 14h7v7l9-11h-7z"
                  />
                </svg>
              </div>
              {{ t(prop.title) }}
            </dt>
            <dd
              class="mt-4 flex flex-auto flex-col text-base leading-7 text-gray-600 dark:text-gray-300"
            >
              <p class="flex-auto">{{ t(prop.description) }}</p>
            </dd>
          </div>
        </dl>
      </div>
    </div>
  </section>
</template>
