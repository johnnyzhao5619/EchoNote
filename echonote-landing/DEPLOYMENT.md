# Landing Deployment

This document describes how `echonote-landing` is deployed to GitHub Pages.

Release baseline: `v1.3.3`

## Deployment Modes

1. Automatic deployment (recommended) via GitHub Actions.
2. Manual build + preview for local validation.

## Automatic Deployment (GitHub Actions)

Workflow file: `echonote-landing/.github/workflows/deploy.yml`

Trigger:

- Push to `main`
- Manual `workflow_dispatch`

Pipeline steps:

1. Install dependencies (`npm ci`)
2. Type check (`npm run type-check`)
3. Build (`npm run build`)
4. Upload `echonote-landing/dist`
5. Deploy to GitHub Pages

Required repository settings:

1. `Settings > Pages`
2. Source: `GitHub Actions`

## Manual Validation

```bash
cd echonote-landing
npm install
npm run build
npm run preview
```

## Base Path

`vite.config.ts` uses:

- `VITE_BASE_PATH` when provided
- fallback: `/EchoNote/`

For non-`EchoNote` repositories, set `VITE_BASE_PATH` in CI/CD to match the real Pages subpath.

## Post-Deploy Checklist

- Site loads under the correct GitHub Pages URL.
- Internal anchors (`#features`, `#how-it-works`, `#github-stats`) work.
- Docs/Issues/Releases/License links point to the current repository.
- GitHub stats section loads data from GitHub API without runtime errors.
