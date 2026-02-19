# CI/CD Guide

本文档描述 EchoNote 当前的 GitHub Actions 流水线结构（已完成去重与版本升级）。

## 目标

- 保持 CI 与发布链路职责单一，避免重复构建/重复发版。
- 所有工作流 Action 版本保持在当前主版本。
- 避免伪分析（mock 质量分）和失效脚本引用。

## 工作流清单

### 1. CI 测试 (`.github/workflows/ci.yml`)

**触发条件：**

- push 到 `main` / `develop`
- pull request 到 `main` / `develop`

**职责：**

1. 三平台测试矩阵：`ubuntu-latest` / `windows-latest` / `macos-latest`
2. 安装平台依赖（含 Linux/macOS 音频相关依赖）
3. 仅对变更的 Python 文件执行增量质量检查（black/isort/flake8/mypy/bandit）
4. 执行测试（覆盖率在 Ubuntu 采集，Windows/macOS 运行稳定性测试）

说明：CI 不再承担 release 事件下的构建职责，避免与发布链路重复。

### 2. 代码质量与安全 (`.github/workflows/quality-check.yml`)

**触发条件：**

- push 到 `main` / `develop`
- pull request 到 `main` / `develop`

**职责：**

- `quality-check`：静态分析与复杂度扫描，产出报告工件
- `i18n-check`：国际化审计 + UI 硬编码文本检查
- `security-check`：Bandit + Safety 安全扫描

说明：已移除固定分数/固定评级这类伪分析输出，报告均来自真实扫描结果。

### 3. 手动构建产物 (`.github/workflows/build.yml`)

**触发条件：**

- `workflow_dispatch`（手动触发）

**职责：**

- 三平台构建：Linux / Windows / macOS（macOS 额外 DMG）
- 上传构建产物（Artifacts）

说明：该工作流不再负责创建 GitHub Release，避免和 `release.yml` 重复。

### 4. 发布 (`.github/workflows/release.yml`)

**触发条件：**

- push tag：`v*.*.*`
- `workflow_dispatch`（仅在 tag ref 下运行）

**职责：**

1. 发布前验证（Ubuntu 上运行测试）
2. 三平台构建并上传产物
3. 生成发布说明（优先使用 `RELEASE_NOTES_<tag>.md`）
4. 创建 GitHub Release 并附加所有产物

说明：发布版本以 tag 为唯一真源，避免手工输入版本导致不一致。

### 5. Landing 页部署 (`.github/workflows/deploy-landing.yml`)

**触发条件：**

- push 到 `main`
- `workflow_dispatch`（仅 `main` ref 会执行构建与部署）

**职责：**

- 构建 `echonote-landing`
- 部署到 GitHub Pages

## 发布操作建议

### 自动发布（推荐）

1. 合并发布代码到目标分支
2. 创建并推送 tag，例如：

```bash
git tag v1.2.0
git push origin v1.2.0
```

3. `release.yml` 自动执行验证、构建与发版

### 手动触发发布

1. 打开 GitHub Actions 的 `Release` 工作流
2. 点击 `Run workflow`
3. 选择一个 `v*.*.*` tag 作为 ref
4. 执行

## 本地排查常用命令

```bash
# 测试
pytest tests/ -v

# 增量或全量质量检查
black --check .
isort --check-only .
flake8 .
mypy .
bandit -c pyproject.toml -r .

# i18n 审计
python scripts/audit_i18n.py --translations-dir=resources/translations
```

## 常见问题

### 1. Linux 构建 PyAudio 失败（缺少 `portaudio.h`）

确保安装了：

- `portaudio19-dev`
- `libasound2-dev`
- `libpulse-dev`

### 2. Windows 控制台 Unicode 编码异常

构建工作流已统一设置：

- `PYTHONUTF8=1`
- `PYTHONIOENCODING=utf-8`

构建脚本日志建议保持 ASCII 输出。

### 3. i18n 检查误报

优先排查是否存在 `setText("硬编码文本")`、`setWindowTitle("硬编码文本")` 或 QMessageBox 直接字面量。

## 维护原则

1. 同类职责只保留一条主链路（避免跨工作流重复实现）
2. 优先删除陈旧脚本引用，而不是保留“兼容占位”
3. 先保证正确性与可维护性，再扩展复杂自动化
