# EchoNote 介绍页（docs/landing）

该目录提供一个无需后端的静态介绍页，用于向团队或社区展示 EchoNote v1.2.0 的能力。页面结构与内容完全开源，可直接部署在 GitHub Pages。所有数据集中存放在 `site-content.json`，避免硬编码与多处维护。

## 目录结构

```
docs/landing/
├── index.html        # 页面骨架，语义化结构 + 无障碍标签
├── styles.css        # 响应式样式，包含暗色主题支持
├── app.js            # 通过 JSON 数据渲染各模块
├── site-content.json # 介绍文案、指标、CTA 等业务数据
└── assets/
    └── echonote-mark.svg
```

## 本地预览

```bash
cd docs/landing
python -m http.server 8080
```

然后访问 <http://localhost:8080>。如需在桌面直接打开，可双击 `index.html`，但个别浏览器会限制本地 `fetch`，建议使用 `http.server`。

## GitHub Pages 部署

1. 在仓库设置中启用 **GitHub Pages**
2. 选择 **Deploy from a branch**
3. 将 **Branch** 设为 `main`（或默认分支），**Folder** 选择 `/docs/landing`
4. 保存后几分钟内即可通过 `https://<组织或用户名>.github.io/<仓库名>/` 访问

介绍页使用纯静态资源，不需要额外构建或依赖安装。若需自定义内容，仅修改 `site-content.json` 即可，版本号等信息会自动同步到页面。

## 与项目版本的关系

- 页面默认展示 `v1.2.0`，与 `pyproject.toml` 及 `RELEASE_NOTES_v1.2.0.md` 保持一致
- 当版本升级时，运行 `scripts/sync_version.py` 后更新 `site-content.json` 中的 `meta.version` 即可

## 可扩展性

- 若要添加新的内容区块，可在 `site-content.json` 中新增字段，并在 `app.js` 中补充渲染函数
- 如需多语言版本，可复制 `site-content.json` 为不同语言文件，再在 `app.js` 中根据 URL 参数加载

欢迎在 PR 中完善文案或样式。如需在公司或社区推广 EchoNote，可直接 Fork 并自定义品牌元素。
