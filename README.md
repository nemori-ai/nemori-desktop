# Nemori

AI-powered personal memory assistant desktop application.

## Architecture

Nemori follows a **frontend-backend separation** architecture:

```
┌─────────────────────────────────────────┐
│         Electron Frontend               │
│  (React + TypeScript + Tailwind CSS)    │
├─────────────────────────────────────────┤
│           Electron Main Process         │
│    (Window management, Backend launch)  │
└─────────────────┬───────────────────────┘
                  │ HTTP/WebSocket
                  ▼
┌─────────────────────────────────────────┐
│          Python Backend                 │
│    (FastAPI + SQLite + ChromaDB)        │
├─────────────────────────────────────────┤
│  - LLM Service (OpenAI compatible)      │
│  - Memory Service (Episodic/Semantic)   │
│  - Screenshot Service                   │
│  - Vector Search (ChromaDB)             │
└─────────────────────────────────────────┘
```

## Features

- **AI Chat**: Conversational interface with memory-augmented responses
- **Memory System**:
  - Episodic memories (events, conversations)
  - Semantic memories (knowledge, preferences)
- **Screenshot Capture**: Automatic screen activity tracking
- **Vector Search**: Semantic similarity search using ChromaDB
- **Local-first**: All data stored locally on your machine

## Prerequisites

- Node.js 18+
- Python 3.10+
- pnpm (recommended) or npm

## Installation

### 1. Install Backend Dependencies

```bash
cd backend
pip install -e .
```

### 2. Install Frontend Dependencies

```bash
cd frontend
pnpm install
# or
npm install
```

## Development

### Start Backend (in one terminal)

```bash
cd backend
python main.py --reload
```

### Start Frontend (in another terminal)

```bash
cd frontend
pnpm dev
# or
npm run dev
```

The application will automatically connect to the backend at `http://127.0.0.1:21978`.

## Configuration

### LLM Settings

Configure your LLM settings in the Settings page of the application. You can configure separate API keys and endpoints for chat and embedding models:

**Chat Model Configuration:**
- Chat API Key
- Chat Base URL (e.g., `https://openrouter.ai/api/v1`)
- Chat Model (recommended: `google/gemini-3-flash-preview`)

**Embedding Model Configuration:**
- Embedding API Key
- Embedding Base URL (e.g., `https://api.openai.com/v1`)
- Embedding Model (recommended: `text-embedding-3-small`)

Or set environment variables:

```bash
# Chat Model
export CHAT_API_KEY="your-chat-api-key"
export CHAT_BASE_URL="https://openrouter.ai/api/v1"
export CHAT_MODEL="google/gemini-3-flash-preview"

# Embedding Model
export EMBEDDING_API_KEY="your-embedding-api-key"
export EMBEDDING_BASE_URL="https://api.openai.com/v1"
export EMBEDDING_MODEL="text-embedding-3-small"
```

### Data Directory

Application data is stored in:
- **macOS/Linux**: `~/.local/share/Nemori/`
- **Windows**: `%APPDATA%/Nemori/`

## Build

### Build for macOS

```bash
cd frontend
pnpm build:mac
```

### Build for Windows

```bash
cd frontend
pnpm build:win
```

### Build for Linux

```bash
cd frontend
pnpm build:linux
```

## Project Structure

```
Nemori/
├── frontend/                 # Electron + React frontend
│   ├── src/
│   │   ├── main/            # Electron main process
│   │   ├── preload/         # IPC bridge
│   │   └── renderer/        # React application
│   │       └── src/
│   │           ├── components/
│   │           ├── pages/
│   │           ├── services/  # API client
│   │           └── ...
│   ├── resources/           # Application resources
│   └── package.json
│
├── backend/                  # Python FastAPI backend
│   ├── api/                 # API routes
│   │   └── routes/
│   ├── services/            # Business logic
│   ├── storage/             # Database & vector store
│   ├── config/              # Configuration
│   ├── models/              # Pydantic schemas
│   ├── main.py              # Entry point
│   └── pyproject.toml
│
└── README.md
```

## API Documentation

When the backend is running, API documentation is available at:
- Swagger UI: http://127.0.0.1:21978/docs
- ReDoc: http://127.0.0.1:21978/redoc

## License

MIT License - see LICENSE file for details.

## Author

[nemori-ai](https://github.com/nemori-ai)
