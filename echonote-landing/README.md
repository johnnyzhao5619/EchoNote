# EchoNote Landing

Vue 3 + TypeScript + Tailwind CSS landing site for EchoNote.

This is the only actively maintained landing implementation.
The old static page under `docs/landing/` is archived and should not receive feature updates.

## Current Architecture

- Single-page landing (`/`) without client-side routing.
- Data-driven sections: Hero, Features, How It Works, GitHub Stats, Footer.
- i18n-first copy: all user-facing text lives in `src/locales/*.json`.
- Centralized link composition through `src/composables/useProjectLinks.ts`.
- Runtime GitHub metrics with short-lived session cache in `src/composables/useGitHubApi.ts`.

## Latest Refactor Highlights

- Removed redundant routing stack (`vue-router`, `src/router`, `src/views/HomeView.vue`).
- Consolidated repeated navigation/resource link logic into one composable.
- Simplified header interaction model (desktop + mobile from one source of truth).
- Reworked style system around shared layout/action/card primitives in `src/assets/main.css`.
- Removed stale and unused source assets/icons/composables.

## Development

```bash
npm install
npm run dev
```

## Quality Checks

```bash
npm run lint
npm run type-check
npm run build
```

## Source of Truth

Keep these files aligned to avoid content or behavior drift:

- `src/config/project.ts`: repository links, SEO metadata, feature order, release tag.
- `src/locales/*.json`: all translatable copy.
- `src/composables/useProjectLinks.ts`: section/resource/quick/footer links.
- `src/composables/useGitHubApi.ts`: GitHub API integration and cache behavior.
- `src/assets/main.css`: shared design tokens and reusable UI utilities.

Do not hardcode copy or repository links directly inside components.

## Asset Policy

- Keep only referenced files in `public/`.
- Prefer one canonical asset per semantic role (logo, banner, og image, favicon).
- Remove generated/legacy source assets in `src/assets/` when no longer referenced.

## Deployment

See `DEPLOYMENT.md` for GitHub Pages setup, base-path strategy, and release checklist.
