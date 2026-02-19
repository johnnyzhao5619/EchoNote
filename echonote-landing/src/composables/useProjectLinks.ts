import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { projectConfig } from '../config/project'
import type { ProjectLinks } from '../types'

type ProjectLinkKey = keyof ProjectLinks

interface ProjectLinkDefinition {
  key: ProjectLinkKey
  labelKey: string
}

interface SectionLinkDefinition {
  id: string
  labelKey: string
}

const SECTION_LINK_DEFINITIONS: SectionLinkDefinition[] = [
  { id: 'features', labelKey: 'nav.features' },
  { id: 'how-it-works', labelKey: 'nav.howItWorks' },
  { id: 'github-stats', labelKey: 'nav.stats' },
]

const HEADER_RESOURCE_LINK_DEFINITIONS: ProjectLinkDefinition[] = [
  { key: 'documentation', labelKey: 'nav.documentation' },
  { key: 'issues', labelKey: 'nav.issues' },
  { key: 'download', labelKey: 'nav.releases' },
]

const HERO_QUICK_LINK_DEFINITIONS: ProjectLinkDefinition[] = [
  { key: 'documentation', labelKey: 'hero.quickLinks.documentation' },
  { key: 'issues', labelKey: 'hero.quickLinks.issues' },
  { key: 'download', labelKey: 'hero.quickLinks.releases' },
  { key: 'license', labelKey: 'hero.quickLinks.license' },
]

const FOOTER_OPEN_SOURCE_LINK_DEFINITIONS: ProjectLinkDefinition[] = [
  { key: 'documentation', labelKey: 'footer.documentation' },
  { key: 'download', labelKey: 'footer.releases' },
  { key: 'issues', labelKey: 'footer.issues' },
  { key: 'contributing', labelKey: 'footer.contributing' },
  { key: 'discussions', labelKey: 'footer.discussions' },
]

const hasHref = (href: string | undefined): href is string => Boolean(href)

const mapProjectLinks = (
  definitions: ProjectLinkDefinition[],
  t: (key: string) => string,
): Array<{ key: ProjectLinkKey; href: string; label: string }> =>
  definitions
    .map((definition) => ({
      key: definition.key,
      href: projectConfig.links[definition.key],
      label: t(definition.labelKey),
    }))
    .filter((item): item is { key: ProjectLinkKey; href: string; label: string } =>
      hasHref(item.href),
    )

export function useProjectLinks() {
  const { t } = useI18n()

  const sectionNav = computed(() =>
    SECTION_LINK_DEFINITIONS.map((section) => ({
      id: section.id,
      href: `#${section.id}`,
      label: t(section.labelKey),
    })),
  )

  const headerResourceNav = computed(() => mapProjectLinks(HEADER_RESOURCE_LINK_DEFINITIONS, t))
  const heroQuickLinks = computed(() => mapProjectLinks(HERO_QUICK_LINK_DEFINITIONS, t))
  const footerOpenSourceLinks = computed(() =>
    mapProjectLinks(FOOTER_OPEN_SOURCE_LINK_DEFINITIONS, t),
  )

  return {
    sectionNav,
    headerResourceNav,
    heroQuickLinks,
    footerOpenSourceLinks,
  }
}
