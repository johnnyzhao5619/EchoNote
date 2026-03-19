<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { projectConfig } from '../config/project'
import SectionHeading from './ui/SectionHeading.vue'

const { t } = useI18n()
</script>

<template>
  <section
    class="py-16 sm:py-24 bg-white dark:bg-gray-900 border-t border-gray-100 dark:border-gray-800"
  >
    <div class="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
      <SectionHeading :title="t('faq.title')" />
      <div class="mx-auto max-w-3xl mt-12 divide-y divide-gray-200 dark:divide-gray-800">
        <details
          v-for="faq in projectConfig.faqs"
          :key="faq.id"
          class="group py-6 [&_summary::-webkit-details-marker]:hidden"
        >
          <summary
            class="flex cursor-pointer items-center justify-between text-gray-900 dark:text-white"
          >
            <h3 class="text-lg font-semibold">{{ t(faq.question) }}</h3>
            <span class="relative ml-4 h-5 w-5 flex-shrink-0 text-gray-500">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                class="absolute inset-0 h-5 w-5 opacity-100 group-open:opacity-0 transition-opacity"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                stroke-width="2"
              >
                <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4" />
              </svg>
              <svg
                xmlns="http://www.w3.org/2000/svg"
                class="absolute inset-0 h-5 w-5 opacity-0 group-open:opacity-100 transition-opacity"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                stroke-width="2"
              >
                <path stroke-linecap="round" stroke-linejoin="round" d="M20 12H4" />
              </svg>
            </span>
          </summary>
          <p class="mt-4 text-base leading-7 text-gray-600 dark:text-gray-300">
            {{ t(faq.answer) }}
          </p>
        </details>
      </div>
    </div>
  </section>
</template>
