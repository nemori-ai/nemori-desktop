# Nemori 构建指南

## Overview

本文档介绍如何构建 Nemori 桌面应用。构建过程分为两个主要部分：后端（Python + PyInstaller）和前端（Electron + electron-builder）。

## Prerequisites

### 必需依赖

| Tool | Version | Purpose |
|------|---------|---------|
| Python | 3.12 | 后端运行环境 |
| Node.js | 20.x+ | 前端运行环境 |
| npm | 9.x+ | 包管理器 |
| pip | Latest | Python 包管理器 |

### 验证依赖

```bash
python3 --version
node --version
npm --version
pip3 --version
```

## Quick Start

使用根目录的 `build.sh` 脚本进行一键构建：

```bash
# 交互式模式
./build.sh

# 命令行模式 - 构建全部
./build.sh --all

# 仅构建后端
./build.sh --backend

# 仅构建前端
./build.sh --frontend

# 清理构建产物
./build.sh --clean
```

## Build Process Details

### 1. 后端构建 (PyInstaller)

后端使用 PyInstaller 打包成独立可执行文件。

#### 目录模式 vs 单文件模式

我们采用**目录模式**而非单文件模式，原因：

| 模式 | 冷启动速度 | 文件大小 | 适用场景 |
|------|-----------|---------|---------|
| 单文件 (onefile) | 慢（需要解压） | 较小 | 简单分发 |
| 目录 (directory) | 快 | 较大 | 桌面应用 |

#### 手动构建后端

```bash
cd backend

# 创建并激活虚拟环境
python3 -m venv .venv
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate   # Windows

# 安装依赖
pip install .
pip install pyinstaller

# 构建
pyinstaller nemori-backend.spec --clean --noconfirm

# 产物位于 dist/nemori-backend/
```

#### PyInstaller Spec 配置

关键配置点（[nemori-backend.spec](../backend/nemori-backend.spec)）：

```python
# 目录模式：EXE 中排除二进制文件
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,  # 关键：排除二进制
    name='nemori-backend',
    ...
)

# 使用 COLLECT 收集所有文件到目录
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    name='nemori-backend',
)
```

#### Hidden Imports

ChromaDB 等依赖需要显式声明 hidden imports：

```python
hiddenimports = [
    # ChromaDB 完整依赖链
    'chromadb',
    'chromadb.config',
    'chromadb.api',
    'chromadb.api.client',
    'chromadb.api.rust',
    'chromadb.telemetry',
    'chromadb.telemetry.product',
    'chromadb.telemetry.product.posthog',
    'chromadb.db',
    'chromadb.db.impl',
    'chromadb.db.impl.sqlite',
    'chromadb.segment',
    'chromadb.segment.impl',
    # ... 更多
]
```

### 2. 前端构建 (Electron)

前端使用 electron-vite 构建，electron-builder 打包。

#### 手动构建前端

```bash
cd frontend

# 安装依赖
npm install

# 构建 + 打包
npm run build

# macOS
npx electron-builder --mac --publish never

# Windows
npx electron-builder --win --publish never

# Linux
npx electron-builder --linux --publish never
```

#### electron-builder 配置

关键配置点（[electron-builder.yml](../frontend/electron-builder.yml)）：

```yaml
# 后端资源路径（目录模式结构）
mac:
  extraResources:
    - from: "../backend-dist/mac/nemori-backend/"
      to: "backend/nemori-backend"
      filter:
        - "**/*"

win:
  extraResources:
    - from: "../backend-dist/win/nemori-backend/"
      to: "backend/nemori-backend"
      filter:
        - "**/*"
```

## Build Output Structure

构建完成后的目录结构：

```
Nemori/
├── backend-dist/
│   ├── mac/
│   │   └── nemori-backend/
│   │       ├── nemori-backend      # 可执行文件
│   │       ├── _internal/          # Python 依赖
│   │       └── ...
│   └── win/
│       └── nemori-backend/
│           ├── nemori-backend.exe
│           └── ...
├── frontend/
│   └── dist/
│       ├── Nemori-1.0.0-arm64.dmg  # macOS ARM64
│       ├── Nemori-1.0.0-x64.dmg    # macOS Intel
│       └── Nemori-1.0.0-setup.exe  # Windows
```

## Runtime Backend Detection

应用启动时，前端会按以下顺序查找后端可执行文件：

```typescript
// BackendService.ts
const candidates = [
  // Resources 目录（打包后）
  join(process.resourcesPath, 'backend', 'nemori-backend', execName),
  join(process.resourcesPath, 'backend', execName),

  // App 目录
  join(app.getAppPath(), '..', 'backend', 'nemori-backend', execName),
  join(app.getAppPath(), 'backend', 'nemori-backend', execName),
]
```

## Port Selection

生产模式下，后端使用随机可用端口启动，避免端口冲突：

```typescript
import { getRandomPort } from 'get-port-please'

// 生产模式
this.port = await getRandomPort(this.host)
```

开发模式下使用固定端口 `21978`。

## Platform-Specific Notes

### macOS

- 支持 x64 (Intel) 和 arm64 (Apple Silicon) 架构
- 构建 Universal Binary：`npx electron-builder --mac`
- 构建特定架构：
  - `npx electron-builder --mac --x64`
  - `npx electron-builder --mac --arm64`

### Windows

- 仅支持 x64 架构
- 输出 NSIS 安装程序

### Linux

- 支持 AppImage、deb、rpm 格式
- 需要额外配置（未完全测试）

## Troubleshooting

### 后端启动失败

1. 检查 PyInstaller hidden imports 是否完整
2. 查看应用日志中的 `[Backend Error]` 输出
3. 确认可执行文件权限：`chmod +x nemori-backend`

### 前端找不到后端

1. 检查 electron-builder.yml 中的 `extraResources` 路径
2. 确认 backend-dist 目录结构正确
3. 检查 BackendService.ts 中的候选路径

### 冷启动慢

确保使用目录模式而非单文件模式构建后端。

## CI/CD

GitHub Actions 工作流配置位于 `.github/workflows/release.yml`（如有）。

发布流程：
1. 创建 Git tag：`git tag v1.0.0`
2. 推送 tag：`git push origin v1.0.0`
3. GitHub Actions 自动构建并创建 Release

## Development Workflow

```bash
# 1. 启动后端（开发模式）
cd backend
source .venv/bin/activate
python main.py --reload

# 2. 启动前端（开发模式）
cd frontend
npm run dev
```

开发模式下，前端会自动寻找并连接到 Python 后端。
