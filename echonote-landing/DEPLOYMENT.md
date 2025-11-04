# Deployment Guide

This document explains how to deploy the EchoNote landing page to GitHub Pages.

## Automatic Deployment

The project is configured with GitHub Actions for automatic deployment to GitHub Pages.

### Setup Requirements

1. **Repository Settings**: Ensure GitHub Pages is enabled in repository settings
   - Go to Settings > Pages
   - Set Source to "GitHub Actions"

2. **Permissions**: The workflow has the necessary permissions configured:
   - `contents: read` - to checkout the code
   - `pages: write` - to deploy to GitHub Pages
   - `id-token: write` - for secure deployment

### Deployment Process

The deployment happens automatically when:

- Code is pushed to the `main` branch
- Manual trigger via GitHub Actions tab

### Workflow Steps

1. **Build Job**:
   - Checkout code
   - Setup Node.js 20
   - Install dependencies
   - Run type checking
   - Build the application
   - Upload build artifacts

2. **Deploy Job**:
   - Deploy artifacts to GitHub Pages
   - Update the live site

## Manual Deployment

For manual deployment or testing:

```bash
# Build for production
npm run build

# Preview the production build locally
npm run preview

# Preview with GitHub Pages base path
npm run preview:github
```

## Configuration Details

### Base Path

- Configured in `vite.config.ts` as `/EchoNote/`
- Matches the GitHub repository name
- Automatically applied to all asset URLs

### Build Optimization

- Code splitting for vendor libraries
- Asset organization by type (images, fonts, etc.)
- Modern browser targeting
- CSS code splitting enabled
- Source maps disabled for production

### Static Files

- `.nojekyll` file included to bypass Jekyll processing
- All public assets copied to build output
- Proper cache headers for static assets

## Troubleshooting

### Common Issues

1. **404 Errors**: Ensure base path matches repository name
2. **Asset Loading**: Check that all assets use relative paths
3. **Router Issues**: Verify router uses `import.meta.env.BASE_URL`

### Verification

After deployment, verify:

- [ ] Site loads at `https://johnnyzhao5619.github.io/EchoNote/`
- [ ] All assets load correctly
- [ ] Navigation works properly
- [ ] SEO meta tags are present
- [ ] Responsive design works on mobile

## Environment Variables

The build uses these environment variables:

- `BASE_URL`: Set automatically by Vite based on config
- `NODE_ENV`: Set to 'production' during build

## Performance

The optimized build includes:

- Vendor chunk separation (Vue, Vue Router, Vue I18n)
- Asset compression and minification
- Modern JavaScript targeting
- Efficient caching strategies
