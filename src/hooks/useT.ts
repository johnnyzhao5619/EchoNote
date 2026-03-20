// src/hooks/useT.ts
//
// Simple i18n hook. Reads locale from settings store, returns a t(key, vars?) function.
// Keys use dot notation: 'models.page_title', 'common.cancel', etc.
// Variable substitution: t('models.download_speed', { speed: '1.2 MB' }) → "1.2 MB/s"

import zhCN from '../../resources/translations/zh_CN.json'
import enUS from '../../resources/translations/en_US.json'
import frFR from '../../resources/translations/fr_FR.json'
import { useSettingsStore } from '../store/settings'

type Translations = typeof zhCN

const TRANSLATIONS: Record<string, Translations> = {
  zh_CN: zhCN,
  en_US: enUS,
  fr_FR: frFR,
}

/**
 * Resolve a dot-separated key in a nested object.
 * e.g. resolve({ a: { b: 'hello' } }, 'a.b') → 'hello'
 */
function resolve(obj: Record<string, unknown>, key: string): string | undefined {
  const parts = key.split('.')
  let cur: unknown = obj
  for (const part of parts) {
    if (cur == null || typeof cur !== 'object') return undefined
    cur = (cur as Record<string, unknown>)[part]
  }
  return typeof cur === 'string' ? cur : undefined
}

/**
 * Substitute `{name}` placeholders in a template string.
 * e.g. substitute('{speed}/s', { speed: '1.2 MB' }) → '1.2 MB/s'
 */
function substitute(template: string, vars: Record<string, string>): string {
  return template.replace(/\{(\w+)\}/g, (_, name) => vars[name] ?? `{${name}}`)
}

/**
 * Returns a translation function `t` for the current locale.
 * Falls back to the key itself if translation is missing.
 */
export function useT() {
  const locale = useSettingsStore((s) => s.config?.locale ?? 'zh_CN')
  const translations = TRANSLATIONS[locale] ?? zhCN

  return function t(key: string, vars?: Record<string, string>): string {
    const value = resolve(translations as Record<string, unknown>, key)
    if (value == null) return key
    if (vars) return substitute(value, vars)
    return value
  }
}
