<p align="center">
  <img src="frontend/resources/icon.png" alt="Nemori Logo" width="128" height="128">
</p>

<h1 align="center">Nemori</h1>

<p align="center">
  <strong>Your AI-powered memory companion that remembers what you do, so you don't have to.</strong>
</p>

<p align="center">
  <a href="https://github.com/nemori-ai/nemori-desktop/releases">
    <img src="https://img.shields.io/github/v/release/nemori-ai/nemori-desktop?style=flat-square" alt="Release">
  </a>
  <a href="https://github.com/nemori-ai/nemori-desktop/blob/main/LICENSE">
    <img src="https://img.shields.io/github/license/nemori-ai/nemori-desktop?style=flat-square" alt="License">
  </a>
  <a href="https://github.com/nemori-ai/nemori-desktop/stargazers">
    <img src="https://img.shields.io/github/stars/nemori-ai/nemori-desktop?style=flat-square" alt="Stars">
  </a>
</p>

<p align="center">
  <a href="./assets/README_CN.md">🇨🇳 中文文档</a>
</p>

---

## ✨ What is Nemori?

Nemori is a **local-first** desktop application that acts as your personal memory assistant. It quietly observes your screen activity, builds a searchable memory of your digital life, and helps you recall anything through natural conversation.

Think of it as having a friendly companion who:
- 📸 **Watches** your screen and takes notes automatically
- 🧠 **Remembers** what you've been working on
- 💬 **Chats** with you about your memories
- 🔒 **Keeps** everything private on your local machine

## 🎯 Features

### 🤖 Desktop Pet
A cute floating companion that lives on your desktop, showing recording status. Right-click for quick access to all features.

<p align="center">
  <img src="assets/screenshot-pet.png" alt="Desktop Pet" width="200">
</p>

### 💬 AI Chat with Memory
Have natural conversations with an AI that actually knows what you've been doing. Two modes available:
- **Chat Mode**: Quick Q&A about your memories - "What was I working on yesterday?"
- **Agent Mode**: Deep analysis with step-by-step reasoning for complex questions

<p align="center">
  <img src="assets/screenshot-chat.png" alt="Chat Interface" width="700">
</p>

### 📖 My Journal
Review your daily activities through an intelligent journal that automatically captures and organizes your screen activity.

<p align="center">
  <img src="assets/screenshot-journal.png" alt="Journal View" width="700">
</p>

### 🧠 Memory Explorer
Browse and search through your episodic memories, semantic knowledge, and personal profile. Memories are automatically categorized into 8 life dimensions: Career, Finance, Health, Family, Social, Growth, Leisure, and Spirit.

<p align="center">
  <img src="assets/screenshot-memories.png" alt="Memory Explorer" width="700">
</p>

### 💡 Insights
Discover patterns in your behavior with AI-generated insights about your work habits, interests, and preferences.

<p align="center">
  <img src="assets/screenshot-insights.png" alt="Insights" width="700">
</p>

### 🔐 Privacy First
- All data stored locally on your machine
- No cloud sync, no tracking
- You control your memories

## 🚀 Quick Start

### 1. Download

Download the latest release for your platform from [GitHub Releases](https://github.com/nemori-ai/nemori-desktop/releases).

| Platform | Download |
|----------|----------|
| macOS (Apple Silicon) | `Nemori-x.x.x-arm64.dmg` |
| macOS (Intel) | `Nemori-x.x.x-x64.dmg` |

### 2. Install

1. Open the DMG and drag Nemori to Applications
2. If you see "Nemori is damaged", run in Terminal:
   ```bash
   xattr -cr /Applications/Nemori.app
   ```

### 3. Configure

1. Open Nemori and go to **Settings**
2. Enter your LLM API credentials (supports OpenAI-compatible APIs)
3. Grant screen recording permission when prompted
4. Click **Start Recording** to begin

<p align="center">
  <img src="assets/screenshot-settings.png" alt="Settings" width="700">
</p>

### 4. Enjoy!

- 🐾 **Summon the pet** from the sidebar to keep Nemori on your desktop
- 💬 **Chat** to ask questions about your activities
- 📖 **Browse journal** to review your day
- 💡 **Check insights** to discover patterns

## ⚙️ Configuration

### LLM Settings

Nemori requires an LLM API for chat and embedding. We recommend [OpenRouter](https://openrouter.ai) for easy access to multiple models.

| Setting | Recommended Value |
|---------|-------------------|
| Chat Model | `google/gemini-3-flash-preview` |
| Embedding Model | `google/gemini-embedding-001` |

### Data Storage

Your data is stored locally:
- **macOS/Linux:** `~/.local/share/Nemori/`
- **Windows:** `%APPDATA%/Nemori/`

## 🛠️ Development

### Prerequisites

- Node.js 18+
- Python 3.12+

### Setup

```bash
# Clone the repository
git clone https://github.com/nemori-ai/nemori-desktop.git
cd nemori-desktop

# Install backend dependencies
cd backend
pip install -e .

# Install frontend dependencies
cd ../frontend
npm install

# Start development
npm run dev
```

### Build

```bash
npm run build:mac
```

## 🏗️ Architecture

```
┌─────────────────────────────────────────┐
│         Electron Frontend               │
│  (React + TypeScript + Tailwind CSS)    │
├─────────────────────────────────────────┤
│           Electron Main Process         │
│   (Window management, Desktop Pet)      │
└─────────────────┬───────────────────────┘
                  │ HTTP/REST
                  ▼
┌─────────────────────────────────────────┐
│          Python Backend                 │
│    (FastAPI + SQLite + ChromaDB)        │
├─────────────────────────────────────────┤
│  • LLM Service (OpenAI compatible)      │
│  • Memory Service (Episodic/Semantic)   │
│  • Screenshot Capture & Analysis        │
│  • Vector Search (ChromaDB)             │
└─────────────────────────────────────────┘
```

## 📄 License

Apache License 2.0 - see [LICENSE](LICENSE) for details.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 💖 Acknowledgments

Built with ❤️ by [nemori-ai](https://github.com/nemori-ai)

### Inspired By

This project was inspired by and references techniques from:

- **[MIRIX](https://github.com/Mirix-AI/MIRIX)** - AI-powered personal memory assistant
- **[MineContext](https://github.com/volcengine/MineContext)** - Context-aware screen understanding
