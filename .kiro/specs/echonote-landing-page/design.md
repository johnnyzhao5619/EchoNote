# EchoNote 项目介绍页面设计文档

## 概述

基于 Vue 3 + Vite + TypeScript 技术栈，为 EchoNote 开源项目开发一个简洁、现代的单页面介绍网站。该页面将采用响应式设计，支持 SEO 优化，并可通过 GitHub Pages 自动部署。

## 技术架构

### 核心技术栈

- **前端框架**: Vue 3 (Composition API)
- **构建工具**: Vite 7.x
- **开发语言**: TypeScript
- **样式框架**: Tailwind CSS v4
- **国际化**: Vue I18n v9
- **部署平台**: GitHub Pages

### 项目结构

```
src/
├── components/          # 可复用组件
│   ├── Header.vue      # 页面头部
│   ├── Hero.vue        # 主要展示区域
│   ├── Features.vue    # 功能特性展示
│   ├── GitHubStats.vue # GitHub统计信息
│   └── Footer.vue      # 页面底部
├── composables/        # 组合式函数
│   ├── useGitHubApi.ts # GitHub API集成
│   └── useSEO.ts       # SEO优化工具
├── assets/             # 静态资源
│   ├── images/         # 图片资源
│   └── styles/         # 全局样式
├── locales/            # 国际化文件
│   ├── zh-CN.json      # 中文
│   └── en-US.json      # 英文
├── types/              # TypeScript类型定义
│   └── github.ts       # GitHub API类型
├── App.vue             # 根组件
└── main.ts             # 应用入口
```

## 组件设计

### 1. Header 组件

**功能**: 页面顶部导航和品牌展示

- 显示 EchoNote Logo 和项目名称
- 包含 GitHub 仓库链接
- 响应式导航菜单
- 语言切换功能

**接口**:

```typescript
interface HeaderProps {
  githubUrl: string;
  showLanguageSwitch?: boolean;
}
```

### 2. Hero 组件

**功能**: 主要展示区域，项目核心信息

- 项目标题和简介
- 主要行动按钮（查看 GitHub、下载等）
- 背景图片或渐变效果
- 项目核心价值主张

**接口**:

```typescript
interface HeroProps {
  title: string;
  description: string;
  primaryAction: ActionButton;
  secondaryAction?: ActionButton;
  backgroundImage?: string;
}

interface ActionButton {
  text: string;
  url: string;
  type: "primary" | "secondary";
}
```

### 3. Features 组件

**功能**: 展示项目主要功能特性

- 网格布局展示功能列表
- 每个功能包含图标、标题和描述
- 支持动画效果
- 响应式布局

**接口**:

```typescript
interface Feature {
  id: string;
  icon: string;
  title: string;
  description: string;
}

interface FeaturesProps {
  features: Feature[];
  columns?: number;
}
```

### 4. GitHubStats 组件

**功能**: 显示 GitHub 仓库统计信息

- Stars、Forks、Issues 数量
- 最新版本信息
- 贡献者数量
- 实时数据获取

**接口**:

```typescript
interface GitHubStats {
  stars: number;
  forks: number;
  issues: number;
  latestRelease?: string;
  contributors: number;
}

interface GitHubStatsProps {
  repository: string;
  refreshInterval?: number;
}
```

### 5. Footer 组件

**功能**: 页面底部信息

- 版权信息
- 相关链接
- 联系方式
- 许可证信息

## 数据模型

### 项目配置

```typescript
interface ProjectConfig {
  name: string;
  description: string;
  githubUrl: string;
  features: Feature[];
  links: {
    documentation?: string;
    demo?: string;
    download?: string;
  };
  seo: {
    title: string;
    description: string;
    keywords: string[];
    ogImage?: string;
  };
}
```

### GitHub API 响应

```typescript
interface GitHubRepository {
  name: string;
  description: string;
  stargazers_count: number;
  forks_count: number;
  open_issues_count: number;
  html_url: string;
  homepage?: string;
  license?: {
    name: string;
    spdx_id: string;
  };
}

interface GitHubRelease {
  tag_name: string;
  name: string;
  published_at: string;
  html_url: string;
}
```

## 样式设计

### 设计系统

- **主色调**: 基于 EchoNote 品牌色彩
- **字体**: 系统字体栈，支持中英文
- **间距**: Tailwind CSS 标准间距系统
- **断点**: 移动优先的响应式设计
  - sm: 640px
  - md: 768px
  - lg: 1024px
  - xl: 1280px

### 组件样式规范

```css
/* 主要按钮样式 */
.btn-primary {
  @apply bg-blue-600 hover:bg-blue-700 text-white px-6 py-3 rounded-lg transition-colors;
}

/* 次要按钮样式 */
.btn-secondary {
  @apply border border-gray-300 hover:border-gray-400 text-gray-700 px-6 py-3 rounded-lg transition-colors;
}

/* 卡片样式 */
.card {
  @apply bg-white rounded-lg shadow-md p-6 hover:shadow-lg transition-shadow;
}
```

## SEO 优化策略

### Meta 标签配置

```html
<meta name="description" content="EchoNote - 开源项目介绍" />
<meta name="keywords" content="EchoNote, 开源, GitHub" />
<meta property="og:title" content="EchoNote" />
<meta property="og:description" content="项目描述" />
<meta property="og:image" content="/og-image.png" />
<meta property="og:url" content="https://johnnyzhao5619.github.io/EchoNote" />
```

### 结构化数据

```json
{
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  "name": "EchoNote",
  "description": "项目描述",
  "url": "https://github.com/johnnyzhao5619/EchoNote",
  "applicationCategory": "DeveloperApplication",
  "operatingSystem": "Cross-platform"
}
```

## 国际化设计

### 语言支持

- 中文 (zh-CN) - 默认语言
- 英文 (en-US) - 国际化支持

### 翻译文件结构

```json
{
  "hero": {
    "title": "EchoNote",
    "description": "项目描述",
    "viewOnGitHub": "查看GitHub"
  },
  "features": {
    "title": "主要特性",
    "items": [...]
  }
}
```

## 错误处理

### GitHub API 错误处理

- 网络请求失败时显示默认数据
- API 限制时显示缓存数据
- 加载状态和错误状态的用户反馈

### 图片加载错误

- 提供默认占位图
- 渐进式图片加载
- 图片加载失败的降级处理

## 部署配置

### GitHub Pages 配置

```yaml
# .github/workflows/deploy.yml
name: Deploy to GitHub Pages
on:
  push:
    branches: [main]
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
      - run: npm ci
      - run: npm run build
      - uses: actions/deploy-pages@v2
```

### Vite 配置

```typescript
// vite.config.ts
export default defineConfig({
  base: "/EchoNote/",
  build: {
    outDir: "dist",
    assetsDir: "assets",
  },
});
```

## 性能优化

### 代码分割

- 路由级别的懒加载
- 组件按需加载
- 第三方库的动态导入

### 资源优化

- 图片压缩和 WebP 格式支持
- CSS 和 JavaScript 压缩
- 静态资源缓存策略

### 加载优化

- 关键资源预加载
- 非关键资源延迟加载
- 服务端渲染考虑（可选）
