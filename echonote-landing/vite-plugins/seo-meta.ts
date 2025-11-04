import type { Plugin } from 'vite'
import { projectConfig, structuredData, githubConfig } from '../src/config/project'

/**
 * Vite插件：动态生成SEO meta标签
 */
export function seoMetaPlugin(): Plugin {
  return {
    name: 'seo-meta',
    transformIndexHtml(html) {
      const { seo } = projectConfig

      // 生成meta标签
      const metaTags = [
        // Primary Meta Tags
        `<title>${seo.title}</title>`,
        `<meta name="title" content="${seo.title}" />`,
        `<meta name="description" content="${seo.description}" />`,
        `<meta name="keywords" content="${seo.keywords.join(', ')}" />`,
        `<meta name="author" content="${githubConfig.owner}" />`,
        `<meta name="robots" content="index, follow" />`,
        `<meta name="language" content="en, zh" />`,
        `<meta name="revisit-after" content="7 days" />`,
        `<meta name="theme-color" content="#3b82f6" />`,

        // Open Graph / Facebook
        `<meta property="og:type" content="website" />`,
        `<meta property="og:url" content="${seo.ogUrl}" />`,
        `<meta property="og:title" content="${seo.title}" />`,
        `<meta property="og:description" content="${seo.description}" />`,
        `<meta property="og:image" content="${seo.ogUrl}${seo.ogImage}" />`,
        `<meta property="og:site_name" content="${projectConfig.name}" />`,
        `<meta property="og:locale" content="zh_CN" />`,
        `<meta property="og:locale:alternate" content="en_US" />`,

        // Twitter
        `<meta property="twitter:card" content="summary_large_image" />`,
        `<meta property="twitter:url" content="${seo.ogUrl}" />`,
        `<meta property="twitter:title" content="${seo.title}" />`,
        `<meta property="twitter:description" content="${seo.description}" />`,
        `<meta property="twitter:image" content="${seo.ogUrl}${seo.ogImage}" />`,
        `<meta name="twitter:site" content="@${projectConfig.name.toLowerCase()}" />`,
        `<meta name="twitter:creator" content="@${githubConfig.owner}" />`,

        // Additional SEO Meta Tags
        `<link rel="canonical" href="${seo.ogUrl}" />`,
        `<link rel="alternate" hreflang="zh-CN" href="${seo.ogUrl}" />`,
        `<link rel="alternate" hreflang="en-US" href="${seo.ogUrl}" />`,
        `<link rel="alternate" hreflang="x-default" href="${seo.ogUrl}" />`,

        // Structured Data (JSON-LD)
        `<script type="application/ld+json">${JSON.stringify(structuredData, null, 2)}</script>`,
      ].join('\n    ')

      // 替换占位符或插入到head中
      return html.replace(/<title>.*?<\/title>/, metaTags)
    },
  }
}
