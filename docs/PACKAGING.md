# Nemori 打包文档

## 架构概述

### 前后端通信架构

Nemori 采用 Electron + Python 后端的架构：

```
┌─────────────────────────────────────────────────────────────┐
│                    Electron App                              │
│  ┌─────────────────┐  IPC  ┌─────────────────────────────┐  │
│  │  Renderer       │◄────►│  Main Process               │  │
│  │  (React UI)     │      │  ├── BackendService         │  │
│  │  ├── api.ts     │      │  ├── ScreenshotService      │  │
│  │  └── pages/     │      │  └── TrayService            │  │
│  └─────────────────┘      └──────────────┬──────────────┘  │
│                                          │                   │
└──────────────────────────────────────────┼───────────────────┘
                                           │ HTTP (dynamic port)
                                           ▼
                              ┌─────────────────────────────┐
                              │   Python Backend            │
                              │   (nemori-backend)          │
                              │   Port: 动态分配            │
                              └─────────────────────────────┘
```

### 动态端口机制

**关键设计**：生产环境使用动态端口，避免端口冲突。

```typescript
// BackendService.ts
// 开发环境：固定端口 21978
// 生产环境：使用 get-port-please 动态分配端口

private async startProduction(): Promise<boolean> {
  this.port = await getRandomPort(this.host)  // 动态获取可用端口
  // ...启动后端
}
```

**端口传递流程**：
1. `BackendService.start()` 获取动态端口
2. `backend:getUrl` IPC handler 返回当前 URL
3. Renderer 的 `api.ts` 调用 `initializeApi()` 获取 URL
4. `ScreenshotService` 通过构造函数接收动态 URL getter

**ScreenshotService 动态端口实现**：

```typescript
// ScreenshotService.ts
export class ScreenshotService {
  private getBackendUrl: () => string

  constructor(getBackendUrl?: () => string) {
    // 接收动态 URL getter，确保每次上传都获取最新端口
    this.getBackendUrl = getBackendUrl || (() => 'http://127.0.0.1:21978')
  }

  private uploadToBackend(imageData: string, monitorId?: string): Promise<void> {
    // 每次上传时动态获取 URL
    const backendUrl = this.getBackendUrl()
    // ...
  }
}

// index.ts
backendService = new BackendService()
await backendService.start()

// 传入动态 getter 而非静态 URL
screenshotService = new ScreenshotService(
  () => backendService?.getUrl() || 'http://127.0.0.1:21978'
)
```

**MineContext 的实现方式对比**：
- MineContext 使用模块级 `getBackendPort()` 函数
- Nemori 使用构造函数注入 getter 函数
- 两种方式都能确保运行时获取最新端口

### 截图权限处理

**macOS 权限问题**：
- 每个进程需要单独的屏幕录制权限
- 如果后端使用 mss 库截图，会产生两个权限请求
- 解决方案：所有截图操作通过 Electron 主进程的 `desktopCapturer` 完成

```
用户看到的权限请求：
✓ Nemori (Electron app) - 主应用权限
✗ nemori-backend (Python) - 不应该出现
```

## 构建步骤

### 环境要求

- Node.js 18+
- Python 3.12
- macOS: Xcode Command Line Tools

### 1. 构建后端

```bash
cd /path/to/Nemori/backend

# 创建 Python 3.12 虚拟环境
python3.12 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
pip install pyinstaller

# 打包（目录模式，更稳定）
pyinstaller nemori-backend.spec
```

后端输出位置：`backend/dist/nemori-backend/nemori-backend`

### 2. 构建前端

```bash
cd /path/to/Nemori/frontend

# 安装依赖
npm install

# 构建
npm run build

# 打包
npx electron-builder --mac --arm64
```

输出位置：`frontend/dist/nemori-{version}-arm64.dmg`

### 3. 完整打包流程

```bash
# 一键构建脚本
cd /path/to/Nemori

# 1. 构建后端
cd backend
source venv/bin/activate
pyinstaller nemori-backend.spec

# 2. 构建前端
cd ../frontend
npm run build
npx electron-builder --mac --arm64
```

## 配置说明

### electron-builder.yml 关键配置

```yaml
extraResources:
  - from: "../backend/dist/nemori-backend"
    to: "backend/nemori-backend"
    filter:
      - "**/*"

mac:
  target:
    - target: dmg
      arch:
        - arm64
  category: public.app-category.productivity
  hardenedRuntime: true
  entitlements: build/entitlements.mac.plist
  entitlementsInherit: build/entitlements.mac.plist
```

### PyInstaller 配置 (nemori-backend.spec)

```python
# 目录模式打包，确保包含所有依赖
a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[],
    # ...
)
exe = EXE(...)
coll = COLLECT(...)  # 目录模式
```

## 常见问题

### Q1: 打包后数据目录不一致

**问题**：开发和生产使用不同数据目录

**解决**：在 `BackendService.ts` 中显式设置 `NEMORI_DATA_DIR`

```typescript
const dataDir = join(homedir(), '.local', 'share', 'Nemori')
this.process = spawn(executablePath, [...], {
  env: { ...process.env, NEMORI_DATA_DIR: dataDir }
})
```

### Q2: 截图权限显示两个 Nemori

**问题**：macOS 权限设置中出现两个 Nemori 条目

**原因**：后端的 mss 库触发了独立的权限请求

**解决**：
1. 所有截图操作移至 Electron 主进程
2. 后端仅接收截图数据并保存
3. 确保后端代码不调用 mss 相关功能

### Q3: 端口冲突

**问题**：多个实例运行时端口冲突

**解决**：
1. 生产环境使用 `get-port-please` 动态分配端口
2. 启动前检查端口是否可用
3. 通过 IPC 将实际端口传递给所有服务

## 测试打包结果

### 清理旧安装

```bash
# 删除应用
rm -rf /Applications/Nemori.app

# 清理缓存（保留数据）
rm -rf ~/Library/Application\ Support/nemori
rm -rf ~/Library/Caches/nemori

# 重置权限（可选）
tccutil reset ScreenCapture
```

### 验证清单

- [ ] 应用能正常启动
- [ ] 后端服务正常运行
- [ ] 截图功能正常（只需授权一次）
- [ ] 数据存储在正确位置 (`~/.local/share/Nemori`)
- [ ] 权限设置中只显示一个 Nemori

## 参考实现

本项目参考了 [MineContext](https://github.com/AiNiee-ChatGPT/MineContext) 的架构设计：

- 动态端口分配：`backend.ts` 中的 `findAvailablePort()`
- 端口传递：通过 IPC handler 暴露 `getBackendPort()`
- 截图服务：完全在 Electron 主进程中实现
