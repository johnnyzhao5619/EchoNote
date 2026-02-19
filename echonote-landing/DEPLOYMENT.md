# Landing Deployment

This document describes how `echonote-landing` is deployed to GitHub Pages.

## Deployment Modes

1. Automatic deployment (recommended) via GitHub Actions.
2. Manual build + preview for local validation.

## Automatic Deployment (GitHub Actions)

Workflow file: `echonote-landing/.github/workflows/deploy.yml`

Trigger:

- Push to `main` under path `echonote-landing/**`
- Manual `workflow_dispatch`

Pipeline steps:

1. Install dependencies (`npm ci`)
2. Type check (`npm run type-check`)
3. Resolve `VITE_BASE_PATH`:
   - Use repository variable `VITE_BASE_PATH` when configured.
   - Otherwise fallback to `/${repository-name}/`.
4. Build (`npm run build`)
5. Upload `echonote-landing/dist`
6. Deploy to GitHub Pages

Required repository settings:

1. `Settings > Pages`
2. Source: `GitHub Actions`

Optional repository variable:

- `VITE_BASE_PATH` (for custom subpath deployments)

## Manual Validation

```bash
cd echonote-landing
npm install
npm run lint
npm run type-check
npm run build
npm run preview
```

## Base Path Strategy

`vite.config.ts` uses the following precedence:

1. `VITE_BASE_PATH`
2. `GITHUB_REPOSITORY` inferred path (e.g. `/EchoNote/`)
3. Local fallback `/`

This removes repository-name hardcoding in source while keeping GitHub Pages compatibility.

## Post-Deploy Checklist

- Site loads under the expected Pages URL.
- Internal anchors (`#features`, `#how-it-works`, `#github-stats`) scroll correctly.
- Docs/Issues/Releases/License links resolve to the current repository.
- GitHub stats section loads repository metrics and release data without runtime errors.
- `<html lang>` matches selected locale after switching language.
