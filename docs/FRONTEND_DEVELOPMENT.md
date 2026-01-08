# Nemori Frontend Development Guide

## Overview

Nemori 桌面应用前端基于 Electron + Vite + React + TypeScript 构建，采用现代化的开发工具链和 UI 设计模式。

## Technology Stack

| Category | Technology | Version |
|----------|------------|---------|
| Framework | Electron | 39.x |
| Build Tool | electron-vite | 5.x |
| UI Library | React | 18.x |
| Language | TypeScript | 5.7+ |
| Styling | Tailwind CSS | 3.4.x |
| UI Components | Radix UI, Ant Design | Latest |
| State Management | Jotai | 2.x |
| Routing | React Router | 7.x |

## Project Structure

```
frontend/
├── src/
│   ├── main/              # Electron main process
│   │   └── index.ts       # Main entry, window management, IPC
│   ├── preload/           # Preload scripts (IPC bridge)
│   │   ├── index.ts       # API exposure to renderer
│   │   └── index.d.ts     # Type declarations for window.api
│   ├── renderer/          # React application
│   │   └── src/
│   │       ├── components/  # Reusable UI components
│   │       ├── pages/       # Page components
│   │       ├── services/    # API services
│   │       ├── assets/      # CSS, images
│   │       └── App.tsx      # Root component
│   ├── shared/            # Shared types between processes
│   └── env.d.ts           # Vite asset type declarations
├── resources/             # App icons, assets
├── electron.vite.config.ts
├── tailwind.config.js
├── tsconfig.json
├── tsconfig.node.json     # Main/preload process config
└── tsconfig.web.json      # Renderer process config
```

## TypeScript Configuration

### Multi-Process Setup

Electron 应用有三个独立的 TypeScript 环境：

1. **Main Process** (`tsconfig.node.json`)
   - Node.js 环境
   - 包含: `src/main/**/*`, `src/preload/**/*`, `src/shared/**/*`

2. **Preload Scripts** (同 `tsconfig.node.json`)
   - 受限的 Node.js 环境
   - 通过 contextBridge 暴露 API

3. **Renderer Process** (`tsconfig.web.json`)
   - 浏览器环境
   - 包含: `src/renderer/src/**/*`, `src/shared/**/*`, `src/preload/index.d.ts`

### Vite Asset Imports

创建 `src/env.d.ts` 声明 Vite 资源导入类型：

```typescript
/// <reference types="electron-vite/node" />

declare module '*?asset' {
  const src: string
  export default src
}

declare module '*.png?asset' {
  const src: string
  export default src
}
```

### Window API Types

在 `src/preload/index.d.ts` 中声明 `window.api` 类型：

```typescript
import { ElectronAPI } from '@electron-toolkit/preload'

declare global {
  interface Window {
    electron: ElectronAPI
    api: {
      window: {
        minimize: () => void
        maximize: () => void
        close: () => void
      }
      backend: {
        getUrl: () => Promise<string>
        start: () => Promise<void>
        stop: () => Promise<void>
      }
    }
  }
}
```

确保 `tsconfig.web.json` 包含此文件：

```json
{
  "include": [
    "src/renderer/src/**/*",
    "src/shared/**/*",
    "src/preload/index.d.ts"
  ]
}
```

## UI/UX Design Patterns

### Design System

Nemori 采用 **Warm Minimalism** 设计风格：

- 温暖的色调 (Warm beige, soft browns)
- 柔和的阴影和圆角
- 玻璃态效果 (Glassmorphism)
- 简洁的布局和留白

### Tailwind Configuration

```javascript
// tailwind.config.js
module.exports = {
  theme: {
    extend: {
      colors: {
        background: 'hsl(var(--background))',
        foreground: 'hsl(var(--foreground))',
        primary: {
          DEFAULT: 'hsl(var(--primary))',
          foreground: 'hsl(var(--primary-foreground))'
        },
        // ... more semantic colors
      },
      boxShadow: {
        'warm-sm': '0 2px 8px -2px rgba(139, 90, 43, 0.08)',
        'warm': '0 4px 16px -4px rgba(139, 90, 43, 0.12)',
        'warm-lg': '0 8px 32px -8px rgba(139, 90, 43, 0.16)'
      }
    }
  }
}
```

### CSS Variables

在 `index.css` 中定义主题变量：

```css
:root {
  --background: 40 30% 96%;
  --foreground: 30 10% 20%;
  --primary: 28 60% 50%;
  --primary-foreground: 40 30% 98%;
  /* ... */
}

.dark {
  --background: 30 15% 10%;
  --foreground: 40 20% 90%;
  /* ... */
}
```

### Glass Effect Components

```css
.glass-sidebar {
  background: rgba(255, 255, 255, 0.7);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border-right: 1px solid rgba(0, 0, 0, 0.06);
}
```

## Electron Window Management

### Frameless Window

```typescript
// main/index.ts
const mainWindow = new BrowserWindow({
  frame: false,
  titleBarStyle: 'hidden',
  trafficLightPosition: { x: 16, y: 16 },
  webPreferences: {
    preload: join(__dirname, '../preload/index.js'),
    contextIsolation: true,
    nodeIntegration: false
  }
})
```

### Custom Title Bar

使用 CSS 类控制拖拽区域：

```css
.drag-region {
  -webkit-app-region: drag;
}

.no-drag {
  -webkit-app-region: no-drag;
}
```

### Platform Detection

```typescript
// Renderer process (no process.platform)
const isMacOS = navigator.userAgent.includes('Mac')
```

## API Service Pattern

### Backend Communication

```typescript
// services/api.ts
class ApiService {
  private baseUrl: string = 'http://127.0.0.1:21978'

  private async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const response = await fetch(`${this.baseUrl}/api${endpoint}`, {
      ...options,
      headers: { 'Content-Type': 'application/json', ...options.headers }
    })
    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
    return response.json()
  }

  // SSE Streaming
  async streamMessage(content: string, onChunk: (chunk: string) => void): Promise<void> {
    const response = await fetch(`${this.baseUrl}/api/chat/stream`, { /* ... */ })
    const reader = response.body?.getReader()
    const decoder = new TextDecoder('utf-8')
    // Process SSE events...
  }
}

export const api = new ApiService()
```

## Common Issues & Solutions

### 1. TypeScript: Cannot find module '*.png?asset'

**问题**: Vite 资源导入类型未声明

**解决**: 创建 `src/env.d.ts` 并在 `tsconfig.node.json` 中包含

### 2. TypeScript: Property 'api' does not exist on type 'Window'

**问题**: `window.api` 类型未声明

**解决**: 在 `tsconfig.web.json` 中包含 `src/preload/index.d.ts`

### 3. Unused Variable Errors

**问题**: TypeScript 严格模式下未使用的变量报错

**解决**: 删除未使用的 import 和变量，或使用 `_` 前缀

### 4. SSE Streaming UTF-8 Issues

**问题**: 多字节 UTF-8 字符被截断

**解决**: 使用 `TextDecoder` 的 `{ stream: true }` 选项

```typescript
const decoder = new TextDecoder('utf-8')
const chunk = decoder.decode(value, { stream: true })
```

### 5. Electron DevTools Autofill Warnings

**问题**: DevTools 控制台显示 Autofill.enable 错误

**解决**: 这是 Chromium DevTools 协议警告，可安全忽略

## Development Workflow

### Commands

```bash
# Development
npm run dev          # Start dev server with hot reload

# Type Checking
npm run typecheck    # Check both node and web configs

# Build
npm run build        # Build for production
npm run build:mac    # Build macOS app
npm run build:win    # Build Windows app

# Code Quality
npm run lint         # ESLint
npm run format       # Prettier
```

### Dependency Updates

更新依赖时注意：

1. **Major Updates**: 检查 breaking changes
   - Tailwind 4.x: 需要完全重写配置
   - React 19.x: 新的并发特性
   - Electron: 检查 Chromium 版本兼容性

2. **Node.js Requirements**:
   - electron-vite 5.x: Node.js 20.19+
   - 部分包需要 Node.js 22.12+

3. **保持稳定的组合**:
   - React 18.x + @types/react 18.x
   - Tailwind 3.x + tailwind.config.js
   - Vite 5.x + electron-vite 5.x

## Performance Considerations

### Bundle Size

- 使用动态导入 (lazy loading) 分割代码
- 避免导入整个库 (`import { Button } from 'antd'` vs `import antd`)

### Rendering

- 使用 `React.memo` 避免不必要的重渲染
- 列表使用虚拟化 (virtualization)
- 图片使用懒加载

### Memory

- 及时清理事件监听器
- SSE/WebSocket 连接在组件卸载时关闭
- 大数据使用分页而非全量加载
