# EchoNote Landing

Vue 3 + TypeScript + Tailwind CSS landing site for EchoNote.

This is the only actively maintained landing implementation.  
The old static page under `docs/landing/` is archived and should not receive feature updates.
The site is intentionally maintained as a single-page landing (`/` only).

## v1.3.0 Highlights

- Single-page information architecture (removed legacy `/about` route and template residue).
- Header navigation hardening across breakpoints (`md`/`lg`/`xl`), including compact `More` menu behavior.
- Fixed narrow-width menu toggle mismatch causing "X only" state.
- Reworked language switcher to stable select control with persisted locale and synchronized `<html lang>`.
- Removed frontend-stack promo section from the landing page to keep product messaging focused.

## Development

```bash
npm install
npm run dev
```

## Build

```bash
npm run build
npm run preview
```

## Source of Truth

To avoid content drift across page and docs, keep these files aligned:

- `src/config/project.ts`: repository links, SEO metadata, feature ordering, release tag.
- `src/locales/*.json`: all user-facing copy (hero, feature cards, workflow, navigation labels).
- `src/composables/useGitHubApi.ts`: runtime repository statistics source (GitHub API).
- `src/i18n/locales.ts`: supported locales and initial locale resolution.

Do not hardcode version strings, release text, or docs links directly inside components.

## UI/UX Baseline

- Unified container and spacing utilities in `src/assets/main.css`: `.site-container`, `.section-shell`.
- Single page heading (`h1`) in hero; section headings use `h2`.
- Keyboard and accessibility support: skip link, focus states, semantic landmarks.
- Locale UX: user-selected language is persisted to `localStorage`, and `<html lang>` is synchronized.
- Open source resource visibility: docs, issues, releases, license, contributing links.

## Deployment

See `DEPLOYMENT.md` for GitHub Pages setup and workflow details.
