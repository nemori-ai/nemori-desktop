# Nemori Agent 功能设计文档

## 1. 概述

Agent 模式是 Nemori 的高级对话模式，能够利用多种记忆搜索工具进行深度和广度搜索，给出最优答案。与普通 Chat 模式相比，Agent 模式具备：

- **工具调用能力**：可以调用多种记忆搜索工具
- **多步推理**：可以进行多轮工具调用和推理
- **可视化过程**：前端实时展示思考过程和工具调用
- **LangChain 兼容**：完全兼容 LangChain 生态系统
- **上下文管理**：采用 SummarizationMiddleware 管理长对话

### 1.1 设计原则

1. **前后端完全分离**：通过 SSE 协议通信，后端不依赖前端实现
2. **LangChain 生态兼容**：工具定义、模型接口均采用 LangChain 标准
3. **协议完整性**：定义完整的事件类型和数据结构
4. **架构分离**：Agent 核心逻辑与 API 层解耦

---

## 2. 核心数据类型

### 2.1 Agent 会话状态 (AgentSession)

```python
# backend/models/agent_schemas.py

from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel
from enum import Enum

class AgentStatus(str, Enum):
    IDLE = "idle"
    THINKING = "thinking"      # Agent 正在思考
    TOOL_CALLING = "tool_calling"  # 正在调用工具
    STREAMING = "streaming"    # 正在流式输出
    COMPLETED = "completed"
    ERROR = "error"

class AgentSession(BaseModel):
    """Agent 会话状态"""
    id: str                              # 会话 ID
    conversation_id: str                 # 关联的对话 ID
    status: AgentStatus
    current_step: int                    # 当前步骤
    max_steps: int = 10                  # 最大步骤数
    created_at: int                      # 创建时间戳
    updated_at: int                      # 更新时间戳
```

### 2.2 工具调用 (ToolCall)

```python
class ToolCallStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    ERROR = "error"

class ToolCall(BaseModel):
    """工具调用记录"""
    id: str                              # 工具调用 ID
    session_id: str                      # Agent 会话 ID
    tool_name: str                       # 工具名称
    tool_args: Dict[str, Any]            # 工具参数
    status: ToolCallStatus
    result: Optional[Any] = None         # 执行结果
    error: Optional[str] = None          # 错误信息
    started_at: Optional[int] = None
    completed_at: Optional[int] = None
    duration_ms: Optional[int] = None    # 执行耗时
```

### 2.3 流式事件 (StreamEvent)

```python
class EventType(str, Enum):
    # Agent 状态事件
    SESSION_START = "session_start"
    SESSION_END = "session_end"

    # 思考过程事件
    THINKING_START = "thinking_start"
    THINKING_CHUNK = "thinking_chunk"    # 思考内容片段
    THINKING_END = "thinking_end"

    # 工具调用事件
    TOOL_CALL_START = "tool_call_start"
    TOOL_CALL_ARGS = "tool_call_args"    # 工具参数（流式）
    TOOL_CALL_RESULT = "tool_call_result"
    TOOL_CALL_ERROR = "tool_call_error"

    # 最终响应事件
    RESPONSE_START = "response_start"
    RESPONSE_CHUNK = "response_chunk"    # 响应内容片段
    RESPONSE_END = "response_end"

    # 错误事件
    ERROR = "error"

class StreamEvent(BaseModel):
    """流式事件"""
    type: EventType
    session_id: str
    timestamp: int
    data: Dict[str, Any]                 # 事件数据

    # 可选字段
    step: Optional[int] = None           # 当前步骤
    tool_call_id: Optional[str] = None   # 关联的工具调用
```

### 2.4 消息格式扩展

```python
class AgentMessage(BaseModel):
    """扩展的消息格式，支持工具调用"""
    id: str
    role: Literal["user", "assistant", "tool"]
    content: Optional[str] = None
    conversation_id: str
    timestamp: int

    # Agent 专属字段
    session_id: Optional[str] = None     # Agent 会话 ID
    tool_calls: Optional[List[ToolCall]] = None  # 工具调用列表
    tool_call_id: Optional[str] = None   # (role=tool时) 对应的工具调用 ID
    thinking: Optional[str] = None       # 思考过程
```

---

## 3. 工具定义

### 3.1 工具接口

```python
# backend/agents/tools/base.py

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from pydantic import BaseModel

class ToolParameter(BaseModel):
    """工具参数定义"""
    name: str
    type: str                            # "string", "integer", "boolean", "array"
    description: str
    required: bool = True
    default: Optional[Any] = None
    enum: Optional[List[Any]] = None     # 枚举值

class ToolDefinition(BaseModel):
    """工具定义"""
    name: str
    description: str
    parameters: List[ToolParameter]

class BaseTool(ABC):
    """工具基类"""

    @property
    @abstractmethod
    def definition(self) -> ToolDefinition:
        """返回工具定义"""
        pass

    @abstractmethod
    async def execute(self, **kwargs) -> Any:
        """执行工具"""
        pass
```

### 3.2 Nemori 记忆搜索工具集

| 工具名称 | 描述 | 参数 |
|---------|------|------|
| `search_episodic_memory` | 搜索情景记忆 | query, limit, time_range |
| `search_semantic_memory` | 搜索语义记忆 | query, category, limit |
| `keyword_search` | 关键词搜索截图/消息 | keywords, source, limit |
| `time_filter` | 按时间范围过滤 | start_time, end_time, type |
| `get_user_profile` | 获取用户画像 | category |
| `search_screenshots` | 搜索截图 | query, app_name, time_range |
| `get_recent_activity` | 获取最近活动 | hours, type |
| `aggregate_insights` | 聚合多个搜索结果 | queries, strategy |

### 3.3 工具实现示例

```python
# backend/agents/tools/memory_tools.py

class SearchEpisodicMemoryTool(BaseTool):
    """情景记忆搜索工具"""

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="search_episodic_memory",
            description="搜索用户的情景记忆（事件、活动、经历）。当需要回忆用户做过什么、发生过什么事时使用。",
            parameters=[
                ToolParameter(
                    name="query",
                    type="string",
                    description="搜索查询，描述要找的记忆内容"
                ),
                ToolParameter(
                    name="limit",
                    type="integer",
                    description="返回结果数量",
                    required=False,
                    default=5
                ),
                ToolParameter(
                    name="time_range",
                    type="object",
                    description="时间范围过滤 {start: timestamp, end: timestamp}",
                    required=False
                )
            ]
        )

    async def execute(self, query: str, limit: int = 5, time_range: Optional[Dict] = None) -> Dict:
        memory_service = MemoryService.get_instance()
        results = await memory_service.search_episodic_memories(
            query=query,
            limit=limit,
            start_time=time_range.get('start') if time_range else None,
            end_time=time_range.get('end') if time_range else None
        )
        return {
            "memories": results,
            "count": len(results),
            "query": query
        }
```

---

## 4. 持久化方案

### 4.1 数据库表设计

```sql
-- Agent 会话表
CREATE TABLE IF NOT EXISTS agent_sessions (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'idle',
    current_step INTEGER DEFAULT 0,
    max_steps INTEGER DEFAULT 10,
    config TEXT,                         -- JSON: 会话配置
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
);

-- 工具调用记录表
CREATE TABLE IF NOT EXISTS tool_calls (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    step INTEGER NOT NULL,               -- 第几步调用
    tool_name TEXT NOT NULL,
    tool_args TEXT NOT NULL,             -- JSON
    status TEXT NOT NULL DEFAULT 'pending',
    result TEXT,                         -- JSON
    error TEXT,
    started_at INTEGER,
    completed_at INTEGER,
    duration_ms INTEGER,
    FOREIGN KEY (session_id) REFERENCES agent_sessions(id)
);

-- Agent 消息表（扩展 messages 表）
CREATE TABLE IF NOT EXISTS agent_messages (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,                  -- user, assistant, tool
    content TEXT,
    thinking TEXT,                       -- 思考过程
    tool_calls TEXT,                     -- JSON: 工具调用列表
    tool_call_id TEXT,                   -- 对应的工具调用 ID
    timestamp INTEGER NOT NULL,
    FOREIGN KEY (session_id) REFERENCES agent_sessions(id)
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_agent_sessions_conversation ON agent_sessions(conversation_id);
CREATE INDEX IF NOT EXISTS idx_tool_calls_session ON tool_calls(session_id);
CREATE INDEX IF NOT EXISTS idx_agent_messages_session ON agent_messages(session_id);
```

### 4.2 向量存储

工具调用结果和 Agent 推理过程可选择性存入向量数据库，用于后续学习和优化。

---

## 5. 后端 API 设计

### 5.1 REST API

```
POST /api/agent/chat            # 发送消息（流式响应）
POST /api/agent/chat/sync       # 发送消息（同步响应）
GET  /api/agent/session/{id}    # 获取会话详情
GET  /api/agent/session/{id}/history  # 获取会话历史
POST /api/agent/session/{id}/cancel   # 取消当前执行
GET  /api/agent/tools           # 获取可用工具列表
```

### 5.2 流式响应格式 (SSE)

```
POST /api/agent/chat
Content-Type: application/json

{
    "content": "用户消息",
    "conversation_id": "可选",
    "config": {
        "max_steps": 10,
        "tools": ["search_episodic_memory", "search_semantic_memory"]
    }
}

Response: text/event-stream

event: session_start
data: {"session_id": "xxx", "conversation_id": "xxx"}

event: thinking_start
data: {"step": 1}

event: thinking_chunk
data: {"content": "让我先搜索..."}

event: tool_call_start
data: {"tool_call_id": "xxx", "tool_name": "search_episodic_memory", "step": 1}

event: tool_call_args
data: {"args": {"query": "...", "limit": 5}}

event: tool_call_result
data: {"tool_call_id": "xxx", "result": {...}, "duration_ms": 150}

event: response_start
data: {"step": 2}

event: response_chunk
data: {"content": "根据搜索结果..."}

event: response_end
data: {"content": "完整响应内容"}

event: session_end
data: {"session_id": "xxx", "total_steps": 2, "tool_calls_count": 1}
```

---

## 6. 前端设计

### 6.1 组件结构

```
frontend/src/renderer/src/
├── pages/
│   └── AgentPage.tsx              # Agent 页面主组件
├── components/
│   └── agent/
│       ├── AgentChat.tsx          # Agent 聊天容器
│       ├── AgentMessage.tsx       # 消息气泡（支持工具调用）
│       ├── ThinkingBlock.tsx      # 思考过程展示
│       ├── ToolCallBlock.tsx      # 工具调用展示
│       ├── ToolResultBlock.tsx    # 工具结果展示
│       └── AgentStatus.tsx        # Agent 状态指示器
└── services/
    └── agentApi.ts                # Agent API 服务
```

### 6.2 TypeScript 类型定义

```typescript
// frontend/src/renderer/src/types/agent.ts

export type EventType =
    | 'session_start' | 'session_end'
    | 'thinking_start' | 'thinking_chunk' | 'thinking_end'
    | 'tool_call_start' | 'tool_call_args' | 'tool_call_result' | 'tool_call_error'
    | 'response_start' | 'response_chunk' | 'response_end'
    | 'error';

export interface StreamEvent {
    type: EventType;
    session_id: string;
    timestamp: number;
    data: Record<string, any>;
    step?: number;
    tool_call_id?: string;
}

export interface ToolCall {
    id: string;
    tool_name: string;
    tool_args: Record<string, any>;
    status: 'pending' | 'running' | 'completed' | 'error';
    result?: any;
    error?: string;
    duration_ms?: number;
}

export interface AgentMessage {
    id: string;
    role: 'user' | 'assistant' | 'tool';
    content?: string;
    thinking?: string;
    tool_calls?: ToolCall[];
    tool_call_id?: string;
    timestamp: number;
    isStreaming?: boolean;
}

export interface AgentSession {
    id: string;
    conversation_id: string;
    status: 'idle' | 'thinking' | 'tool_calling' | 'streaming' | 'completed' | 'error';
    current_step: number;
    max_steps: number;
}
```

### 6.3 UI 设计要点

```
┌─────────────────────────────────────────────────────────────┐
│  Agent Mode                                    [Tools ▼]    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 👤 用户消息                                          │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 🤖 Agent                                             │   │
│  │                                                       │   │
│  │ ┌─ 💭 思考过程 ──────────────────────────────────┐   │   │
│  │ │ 让我搜索用户的情景记忆来找到相关信息...         │   │   │
│  │ └─────────────────────────────────────────────────┘   │   │
│  │                                                       │   │
│  │ ┌─ 🔧 工具调用: search_episodic_memory ──────────┐   │   │
│  │ │ 参数: { "query": "...", "limit": 5 }            │   │   │
│  │ │ ────────────────────────────────────            │   │   │
│  │ │ ✅ 结果: 找到 3 条相关记忆                       │   │   │
│  │ │ • 记忆1: ...                                     │   │   │
│  │ │ • 记忆2: ...                                     │   │   │
│  │ │ ⏱️ 耗时: 150ms                                   │   │   │
│  │ └─────────────────────────────────────────────────┘   │   │
│  │                                                       │   │
│  │ 根据搜索到的记忆，我发现...                          │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│  [输入消息...]                                    [发送]   │
└─────────────────────────────────────────────────────────────┘
```

### 6.4 流式渲染状态机

```typescript
// 消息渲染状态
type RenderState = {
    thinking: string;           // 累积的思考内容
    toolCalls: Map<string, ToolCall>;  // 工具调用状态
    response: string;           // 累积的响应内容
    currentPhase: 'idle' | 'thinking' | 'tool_calling' | 'responding';
};

// 事件处理
function handleStreamEvent(event: StreamEvent, state: RenderState): RenderState {
    switch (event.type) {
        case 'thinking_chunk':
            return { ...state, thinking: state.thinking + event.data.content };
        case 'tool_call_start':
            state.toolCalls.set(event.tool_call_id!, {
                id: event.tool_call_id!,
                tool_name: event.data.tool_name,
                tool_args: {},
                status: 'running'
            });
            return { ...state, currentPhase: 'tool_calling' };
        case 'tool_call_result':
            const tc = state.toolCalls.get(event.tool_call_id!);
            if (tc) {
                tc.status = 'completed';
                tc.result = event.data.result;
                tc.duration_ms = event.data.duration_ms;
            }
            return state;
        case 'response_chunk':
            return { ...state, response: state.response + event.data.content };
        // ...
    }
}
```

---

## 7. Agent 执行引擎

### 7.1 核心循环

```python
# backend/agents/agent_executor.py

class AgentExecutor:
    """Agent 执行引擎"""

    def __init__(self, tools: List[BaseTool], llm: LLMService):
        self.tools = {t.definition.name: t for t in tools}
        self.llm = llm

    async def run(
        self,
        messages: List[Dict],
        session: AgentSession,
        on_event: Callable[[StreamEvent], None]
    ) -> str:
        """执行 Agent 循环"""

        while session.current_step < session.max_steps:
            session.current_step += 1

            # 1. 调用 LLM 获取下一步行动
            on_event(StreamEvent(type=EventType.THINKING_START, ...))

            response = await self.llm.chat_with_tools(
                messages=messages,
                tools=[t.definition for t in self.tools.values()],
                stream=True
            )

            # 2. 处理响应
            if response.tool_calls:
                # 执行工具调用
                for tool_call in response.tool_calls:
                    on_event(StreamEvent(type=EventType.TOOL_CALL_START, ...))

                    result = await self.execute_tool(tool_call)

                    on_event(StreamEvent(type=EventType.TOOL_CALL_RESULT, ...))

                    # 将结果添加到消息历史
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(result)
                    })
            else:
                # 最终响应
                on_event(StreamEvent(type=EventType.RESPONSE_END, ...))
                return response.content

        return "达到最大步骤数限制"
```

### 7.2 系统提示词

```python
AGENT_SYSTEM_PROMPT = """你是 Nemori，一个智能的个人记忆助手。你可以使用以下工具来搜索和分析用户的记忆：

## 可用工具

{tools_description}

## 工作流程

1. 分析用户的问题，确定需要搜索什么类型的记忆
2. 使用合适的工具进行搜索
3. 如果需要，进行多轮搜索以获取更完整的信息
4. 综合所有搜索结果，给出准确、有帮助的回答

## 注意事项

- 优先使用语义搜索获取相关记忆
- 如果语义搜索结果不足，尝试关键词搜索
- 注意时间范围，用户可能在询问特定时间段的事情
- 回答要基于实际搜索到的记忆，不要编造

当前时间：{current_time}
"""
```

---

## 8. 开发阶段计划

### Phase 1: 基础架构 (Week 1)
- [ ] 定义所有数据类型和 Pydantic 模型
- [ ] 创建数据库表和迁移
- [ ] 实现基础工具接口
- [ ] 实现 Agent 执行引擎核心循环

### Phase 2: 工具实现 (Week 2)
- [ ] 实现 search_episodic_memory
- [ ] 实现 search_semantic_memory
- [ ] 实现 keyword_search
- [ ] 实现 time_filter
- [ ] 实现 get_user_profile
- [ ] 实现 get_recent_activity

### Phase 3: API 层 (Week 3)
- [ ] 实现 SSE 流式响应
- [ ] 实现 Agent 会话管理 API
- [ ] 实现工具列表 API
- [ ] 添加错误处理和重试机制

### Phase 4: 前端实现 (Week 4)
- [ ] 创建 AgentPage 和相关组件
- [ ] 实现 SSE 客户端和状态管理
- [ ] 实现工具调用可视化
- [ ] 实现思考过程展示
- [ ] 添加到侧边栏导航

### Phase 5: 优化和测试 (Week 5)
- [ ] 性能优化
- [ ] 错误处理完善
- [ ] 用户体验优化
- [ ] 集成测试

---

## 9. 技术决策总结

| 决策点 | 选择 | 理由 |
|-------|------|------|
| Agent 框架 | 自研简化版 | 参考 deepagents 但保持轻量 |
| 流式协议 | SSE | 简单、兼容性好 |
| 工具定义 | Pydantic + JSON Schema | 类型安全、LLM 友好 |
| 持久化 | SQLite | 与现有系统一致 |
| 前端状态 | React useState + useReducer | 简单场景足够 |
| 消息格式 | OpenAI 兼容 + 扩展 | 方便切换模型 |

---

## 10. LangChain 兼容性设计

### 10.1 工具定义兼容

```python
# backend/agents/tools/langchain_compat.py

from langchain_core.tools import BaseTool, StructuredTool
from langchain_core.callbacks import CallbackManagerForToolRun
from pydantic import BaseModel, Field
from typing import Optional, Type

class SearchEpisodicMemoryInput(BaseModel):
    """情景记忆搜索输入"""
    query: str = Field(description="搜索查询")
    limit: int = Field(default=5, description="返回结果数量")
    time_range: Optional[dict] = Field(default=None, description="时间范围")

class SearchEpisodicMemoryTool(BaseTool):
    """LangChain 兼容的情景记忆搜索工具"""
    name: str = "search_episodic_memory"
    description: str = "搜索用户的情景记忆（事件、活动、经历）"
    args_schema: Type[BaseModel] = SearchEpisodicMemoryInput

    def _run(
        self,
        query: str,
        limit: int = 5,
        time_range: Optional[dict] = None,
        run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> dict:
        """同步执行"""
        import asyncio
        return asyncio.run(self._arun(query, limit, time_range, run_manager))

    async def _arun(
        self,
        query: str,
        limit: int = 5,
        time_range: Optional[dict] = None,
        run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> dict:
        """异步执行"""
        from services.memory_service import MemoryService
        memory = MemoryService.get_instance()
        results = await memory.search_episodic_memories(query, limit)
        return {"memories": results, "count": len(results)}
```

### 10.2 模型接口兼容

```python
# backend/agents/model_adapter.py

from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI
from services.llm_service import LLMService

def create_chat_model() -> BaseChatModel:
    """创建 LangChain 兼容的聊天模型"""
    llm = LLMService.get_instance()

    return ChatOpenAI(
        api_key=llm._chat_api_key,
        base_url=llm._chat_base_url,
        model=llm._chat_model,
        streaming=True
    )
```

### 10.3 SummarizationMiddleware 上下文管理

```python
# backend/agents/middleware/summarization.py

from typing import List, Dict, Any
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, AIMessage

class SummarizationMiddleware:
    """上下文摘要中间件，防止超出上下文限制"""

    def __init__(
        self,
        max_tokens: int = 100000,
        summarize_threshold: int = 80000,
        preserve_recent: int = 10
    ):
        self.max_tokens = max_tokens
        self.summarize_threshold = summarize_threshold
        self.preserve_recent = preserve_recent

    async def process_messages(
        self,
        messages: List[BaseMessage],
        llm: BaseChatModel
    ) -> List[BaseMessage]:
        """处理消息列表，必要时进行摘要"""
        token_count = self._estimate_tokens(messages)

        if token_count < self.summarize_threshold:
            return messages

        # 保留系统消息和最近的消息
        system_messages = [m for m in messages if isinstance(m, SystemMessage)]
        recent_messages = messages[-self.preserve_recent:]
        old_messages = messages[len(system_messages):-self.preserve_recent]

        if not old_messages:
            return messages

        # 生成摘要
        summary = await self._summarize(old_messages, llm)

        return system_messages + [
            SystemMessage(content=f"[对话历史摘要]\n{summary}")
        ] + recent_messages

    async def _summarize(
        self,
        messages: List[BaseMessage],
        llm: BaseChatModel
    ) -> str:
        """生成消息摘要"""
        content = "\n".join([
            f"{m.type}: {m.content[:500]}" for m in messages
        ])

        response = await llm.ainvoke([
            SystemMessage(content="请简洁地摘要以下对话内容，保留关键信息和上下文："),
            HumanMessage(content=content)
        ])

        return response.content

    def _estimate_tokens(self, messages: List[BaseMessage]) -> int:
        """估算 token 数量"""
        total_chars = sum(len(m.content) for m in messages)
        return total_chars // 4  # 粗略估算
```

---

## 11. UI 优化设计（参考 Claude/MineContext 风格）

### 11.1 消息样式改进

**核心原则**：AI 消息不使用对话框包裹，采用更简洁的设计

```typescript
// frontend/src/renderer/src/components/chat/Message.tsx

interface MessageProps {
  role: 'user' | 'assistant'
  content: string
  thinking?: string
  toolCalls?: ToolCall[]
  isStreaming?: boolean
}

export function Message({ role, content, thinking, toolCalls, isStreaming }: MessageProps) {
  const isUser = role === 'user'

  return (
    <div className={cn(
      'group flex w-full py-4',
      isUser ? 'justify-end' : 'justify-start'
    )}>
      <div className={cn(
        'flex flex-col gap-2 max-w-[80%]',
        isUser ? 'items-end' : 'items-start'
      )}>
        {/* 用户消息：保留气泡样式 */}
        {isUser ? (
          <div className="rounded-2xl px-4 py-3 bg-primary text-primary-foreground">
            <p className="text-sm whitespace-pre-wrap">{content}</p>
          </div>
        ) : (
          /* AI 消息：无边框，直接渲染 */
          <div className="w-full">
            {/* 思考过程 - 可折叠 */}
            {thinking && (
              <ThinkingBlock content={thinking} isStreaming={isStreaming} />
            )}

            {/* 工具调用 - 折叠面板 */}
            {toolCalls?.map(tc => (
              <ToolCallBlock key={tc.id} toolCall={tc} />
            ))}

            {/* 主要内容 - 无边框 */}
            <div className="prose prose-sm max-w-none text-foreground">
              <MarkdownContent content={content} />
              {isStreaming && (
                <span className="inline-block w-2 h-4 bg-primary/70 animate-pulse ml-0.5" />
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
```

### 11.2 字体和排版优化

```css
/* frontend/src/renderer/src/assets/index.css */

/* 基础字体配置 */
body {
  font-family:
    Inter,
    -apple-system,
    BlinkMacSystemFont,
    'Segoe UI',
    Roboto,
    'Helvetica Neue',
    sans-serif;
  text-rendering: optimizeLegibility;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

/* Markdown 内容样式 */
.prose {
  line-height: 1.7;
  color: hsl(var(--foreground));
}

.prose p {
  margin: 0.75em 0;
}

.prose h1, .prose h2, .prose h3 {
  font-weight: 600;
  line-height: 1.3;
  margin-top: 1.5em;
  margin-bottom: 0.5em;
}

.prose code {
  font-family:
    ui-monospace,
    SFMono-Regular,
    'SF Mono',
    Menlo,
    Consolas,
    monospace;
  font-size: 0.875em;
  padding: 0.2em 0.4em;
  border-radius: 0.25rem;
  background: hsl(var(--muted));
}

.prose pre {
  background: hsl(var(--muted));
  border-radius: 0.5rem;
  padding: 1rem;
  overflow-x: auto;
}

.prose pre code {
  background: transparent;
  padding: 0;
}

/* AI 消息无边框样式 */
.message-assistant {
  background: transparent;
  border: none;
}
```

### 11.3 思考过程组件（折叠面板）

```typescript
// frontend/src/renderer/src/components/agent/ThinkingBlock.tsx

import { useState } from 'react'
import { ChevronDown, Brain } from 'lucide-react'
import { cn } from '@/lib/utils'

interface ThinkingBlockProps {
  content: string
  isStreaming?: boolean
  duration?: number
}

export function ThinkingBlock({ content, isStreaming, duration }: ThinkingBlockProps) {
  const [isOpen, setIsOpen] = useState(false)

  return (
    <div className="mb-3">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
      >
        <Brain className="w-4 h-4" />
        {isStreaming ? (
          <span className="flex items-center gap-1">
            Thinking
            <span className="flex gap-0.5">
              <span className="w-1 h-1 bg-current rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
              <span className="w-1 h-1 bg-current rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
              <span className="w-1 h-1 bg-current rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
            </span>
          </span>
        ) : (
          <span>Thought for {duration || 0}s</span>
        )}
        <ChevronDown className={cn(
          'w-4 h-4 transition-transform',
          isOpen && 'rotate-180'
        )} />
      </button>

      {isOpen && (
        <div className="mt-2 pl-6 border-l-2 border-muted text-sm text-muted-foreground">
          {content}
        </div>
      )}
    </div>
  )
}
```

### 11.4 工具调用组件（折叠面板）

```typescript
// frontend/src/renderer/src/components/agent/ToolCallBlock.tsx

import { useState } from 'react'
import { ChevronDown, Wrench, Check, X, Loader2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { ToolCall } from '@/types/agent'

interface ToolCallBlockProps {
  toolCall: ToolCall
}

export function ToolCallBlock({ toolCall }: ToolCallBlockProps) {
  const [isOpen, setIsOpen] = useState(false)

  const StatusIcon = {
    pending: Loader2,
    running: Loader2,
    completed: Check,
    error: X
  }[toolCall.status]

  const statusColor = {
    pending: 'text-muted-foreground',
    running: 'text-blue-500',
    completed: 'text-green-500',
    error: 'text-red-500'
  }[toolCall.status]

  return (
    <div className="mb-3 rounded-lg border border-border bg-muted/30 overflow-hidden">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-muted/50 transition-colors"
      >
        <Wrench className="w-4 h-4 text-muted-foreground" />
        <span className="font-medium">{toolCall.tool_name}</span>
        <StatusIcon className={cn(
          'w-4 h-4 ml-auto',
          statusColor,
          toolCall.status === 'running' && 'animate-spin'
        )} />
        {toolCall.duration_ms && (
          <span className="text-xs text-muted-foreground">
            {toolCall.duration_ms}ms
          </span>
        )}
        <ChevronDown className={cn(
          'w-4 h-4 text-muted-foreground transition-transform',
          isOpen && 'rotate-180'
        )} />
      </button>

      {isOpen && (
        <div className="px-3 pb-3 space-y-2">
          {/* 参数 */}
          <div>
            <div className="text-xs font-medium text-muted-foreground mb-1">参数</div>
            <pre className="text-xs bg-muted rounded p-2 overflow-x-auto">
              {JSON.stringify(toolCall.tool_args, null, 2)}
            </pre>
          </div>

          {/* 结果 */}
          {toolCall.result && (
            <div>
              <div className="text-xs font-medium text-muted-foreground mb-1">结果</div>
              <pre className="text-xs bg-muted rounded p-2 overflow-x-auto max-h-48">
                {JSON.stringify(toolCall.result, null, 2)}
              </pre>
            </div>
          )}

          {/* 错误 */}
          {toolCall.error && (
            <div className="text-xs text-red-500 bg-red-50 dark:bg-red-950/20 rounded p-2">
              {toolCall.error}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
```

### 11.5 Chat/Agent 模式切换

```typescript
// frontend/src/renderer/src/components/chat/ModeToggle.tsx

interface ModeToggleProps {
  mode: 'chat' | 'agent'
  onModeChange: (mode: 'chat' | 'agent') => void
}

export function ModeToggle({ mode, onModeChange }: ModeToggleProps) {
  return (
    <div className="inline-flex rounded-lg border border-border p-1 bg-muted/30">
      <button
        onClick={() => onModeChange('chat')}
        className={cn(
          'px-3 py-1.5 text-sm rounded-md transition-colors',
          mode === 'chat'
            ? 'bg-background text-foreground shadow-sm'
            : 'text-muted-foreground hover:text-foreground'
        )}
      >
        Chat
      </button>
      <button
        onClick={() => onModeChange('agent')}
        className={cn(
          'px-3 py-1.5 text-sm rounded-md transition-colors',
          mode === 'agent'
            ? 'bg-background text-foreground shadow-sm'
            : 'text-muted-foreground hover:text-foreground'
        )}
      >
        Agent
      </button>
    </div>
  )
}
```

---

## 12. 前后端分离架构

### 12.1 后端架构

```
backend/
├── agents/                    # Agent 核心模块
│   ├── __init__.py
│   ├── executor.py           # Agent 执行引擎
│   ├── tools/                # 工具集
│   │   ├── __init__.py
│   │   ├── base.py          # 工具基类
│   │   ├── memory_tools.py  # 记忆搜索工具
│   │   └── langchain_compat.py  # LangChain 兼容层
│   ├── middleware/           # 中间件
│   │   ├── __init__.py
│   │   └── summarization.py # 上下文摘要
│   └── model_adapter.py     # 模型适配器
├── api/
│   └── routes/
│       └── agent.py         # Agent API 路由
├── models/
│   └── agent_schemas.py     # Agent 数据模型
└── storage/
    └── agent_store.py       # Agent 持久化
```

### 12.2 前端架构

```
frontend/src/renderer/src/
├── pages/
│   └── ChatPage.tsx          # 统一的聊天页面（支持 Chat/Agent 切换）
├── components/
│   ├── chat/                 # 通用聊天组件
│   │   ├── Message.tsx      # 消息组件（重构）
│   │   ├── MessageList.tsx  # 消息列表
│   │   ├── InputArea.tsx    # 输入区域
│   │   ├── ModeToggle.tsx   # 模式切换
│   │   └── MarkdownContent.tsx  # Markdown 渲染
│   └── agent/                # Agent 专属组件
│       ├── ThinkingBlock.tsx    # 思考过程
│       ├── ToolCallBlock.tsx    # 工具调用
│       └── AgentStatus.tsx      # 状态指示
├── services/
│   ├── api.ts               # 基础 API
│   └── agentApi.ts          # Agent API
├── hooks/
│   └── useAgentStream.ts    # Agent 流式处理 Hook
└── types/
    └── agent.ts             # Agent 类型定义
```

### 12.3 完整 SSE 协议定义

```typescript
// 前端类型定义 - frontend/src/renderer/src/types/agent.ts

/**
 * SSE 事件类型枚举
 */
export enum EventType {
  // 会话生命周期
  SESSION_START = 'session_start',
  SESSION_END = 'session_end',

  // 思考过程
  THINKING_START = 'thinking_start',
  THINKING_CHUNK = 'thinking_chunk',
  THINKING_END = 'thinking_end',

  // 工具调用
  TOOL_CALL_START = 'tool_call_start',
  TOOL_CALL_ARGS = 'tool_call_args',
  TOOL_CALL_RESULT = 'tool_call_result',
  TOOL_CALL_ERROR = 'tool_call_error',

  // 响应输出
  RESPONSE_START = 'response_start',
  RESPONSE_CHUNK = 'response_chunk',
  RESPONSE_END = 'response_end',

  // 错误
  ERROR = 'error'
}

/**
 * 基础事件结构
 */
export interface BaseEvent {
  type: EventType
  session_id: string
  timestamp: number
  step?: number
}

/**
 * 会话开始事件
 */
export interface SessionStartEvent extends BaseEvent {
  type: EventType.SESSION_START
  data: {
    conversation_id: string
    max_steps: number
    tools: string[]
  }
}

/**
 * 思考内容事件
 */
export interface ThinkingChunkEvent extends BaseEvent {
  type: EventType.THINKING_CHUNK
  data: {
    content: string
  }
}

/**
 * 工具调用开始事件
 */
export interface ToolCallStartEvent extends BaseEvent {
  type: EventType.TOOL_CALL_START
  data: {
    tool_call_id: string
    tool_name: string
  }
}

/**
 * 工具调用结果事件
 */
export interface ToolCallResultEvent extends BaseEvent {
  type: EventType.TOOL_CALL_RESULT
  data: {
    tool_call_id: string
    result: any
    duration_ms: number
  }
}

/**
 * 响应内容事件
 */
export interface ResponseChunkEvent extends BaseEvent {
  type: EventType.RESPONSE_CHUNK
  data: {
    content: string
  }
}

/**
 * 会话结束事件
 */
export interface SessionEndEvent extends BaseEvent {
  type: EventType.SESSION_END
  data: {
    total_steps: number
    tool_calls_count: number
    total_duration_ms: number
  }
}

/**
 * 错误事件
 */
export interface ErrorEvent extends BaseEvent {
  type: EventType.ERROR
  data: {
    code: string
    message: string
    recoverable: boolean
  }
}

/**
 * 联合类型
 */
export type StreamEvent =
  | SessionStartEvent
  | ThinkingChunkEvent
  | ToolCallStartEvent
  | ToolCallResultEvent
  | ResponseChunkEvent
  | SessionEndEvent
  | ErrorEvent
  // ... 其他事件类型
```

### 12.4 后端 SSE 实现

```python
# backend/api/routes/agent.py

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List
import json
import asyncio

router = APIRouter()

class AgentChatRequest(BaseModel):
    content: str
    conversation_id: Optional[str] = None
    config: Optional[dict] = None  # max_steps, tools 等

@router.post("/chat")
async def agent_chat(request: AgentChatRequest):
    """Agent 聊天端点 - SSE 流式响应"""

    async def event_generator():
        from agents.executor import AgentExecutor
        from agents.tools import get_all_tools
        from models.agent_schemas import AgentSession

        # 创建会话
        session = AgentSession.create(
            conversation_id=request.conversation_id,
            max_steps=request.config.get('max_steps', 10) if request.config else 10
        )

        # 发送会话开始事件
        yield format_sse_event('session_start', {
            'session_id': session.id,
            'conversation_id': session.conversation_id,
            'max_steps': session.max_steps,
            'tools': [t.name for t in get_all_tools()]
        })

        # 创建执行器
        executor = AgentExecutor(
            tools=get_all_tools(),
            session=session
        )

        # 事件回调
        async def on_event(event_type: str, data: dict):
            yield format_sse_event(event_type, {
                **data,
                'session_id': session.id,
                'step': session.current_step,
                'timestamp': int(time.time() * 1000)
            })

        # 执行 Agent
        try:
            async for event in executor.run_stream(request.content):
                yield format_sse_event(event.type, event.data)
        except Exception as e:
            yield format_sse_event('error', {
                'code': 'EXECUTION_ERROR',
                'message': str(e),
                'recoverable': False
            })

        # 发送会话结束事件
        yield format_sse_event('session_end', {
            'session_id': session.id,
            'total_steps': session.current_step,
            'tool_calls_count': session.tool_calls_count,
            'total_duration_ms': session.duration_ms
        })

    return StreamingResponse(
        event_generator(),
        media_type='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no'
        }
    )

def format_sse_event(event_type: str, data: dict) -> str:
    """格式化 SSE 事件"""
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
```

### 12.5 前端 SSE 处理 Hook

```typescript
// frontend/src/renderer/src/hooks/useAgentStream.ts

import { useState, useCallback, useRef } from 'react'
import type { StreamEvent, ToolCall, AgentMessage } from '@/types/agent'

interface UseAgentStreamOptions {
  onSessionStart?: (data: any) => void
  onSessionEnd?: (data: any) => void
  onError?: (error: any) => void
}

interface AgentState {
  isStreaming: boolean
  currentStep: number
  thinking: string
  toolCalls: Map<string, ToolCall>
  response: string
  messages: AgentMessage[]
}

export function useAgentStream(options: UseAgentStreamOptions = {}) {
  const [state, setState] = useState<AgentState>({
    isStreaming: false,
    currentStep: 0,
    thinking: '',
    toolCalls: new Map(),
    response: '',
    messages: []
  })

  const abortControllerRef = useRef<AbortController | null>(null)

  const sendMessage = useCallback(async (
    content: string,
    conversationId?: string,
    config?: { max_steps?: number; tools?: string[] }
  ) => {
    // 取消之前的请求
    abortControllerRef.current?.abort()
    abortControllerRef.current = new AbortController()

    setState(prev => ({
      ...prev,
      isStreaming: true,
      thinking: '',
      response: '',
      toolCalls: new Map()
    }))

    try {
      const response = await fetch('/api/agent/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content, conversation_id: conversationId, config }),
        signal: abortControllerRef.current.signal
      })

      const reader = response.body?.getReader()
      const decoder = new TextDecoder()

      if (!reader) throw new Error('No response body')

      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.startsWith('event: ')) {
            const eventType = line.slice(7)
            continue
          }
          if (line.startsWith('data: ')) {
            const data = JSON.parse(line.slice(6))
            handleEvent({ type: data.type || eventType, ...data })
          }
        }
      }
    } catch (error) {
      if ((error as Error).name !== 'AbortError') {
        options.onError?.(error)
      }
    } finally {
      setState(prev => ({ ...prev, isStreaming: false }))
    }
  }, [options])

  const handleEvent = useCallback((event: StreamEvent) => {
    switch (event.type) {
      case 'session_start':
        options.onSessionStart?.(event.data)
        break

      case 'thinking_chunk':
        setState(prev => ({
          ...prev,
          thinking: prev.thinking + event.data.content
        }))
        break

      case 'tool_call_start':
        setState(prev => {
          const newToolCalls = new Map(prev.toolCalls)
          newToolCalls.set(event.data.tool_call_id, {
            id: event.data.tool_call_id,
            tool_name: event.data.tool_name,
            tool_args: {},
            status: 'running'
          })
          return { ...prev, toolCalls: newToolCalls }
        })
        break

      case 'tool_call_result':
        setState(prev => {
          const newToolCalls = new Map(prev.toolCalls)
          const tc = newToolCalls.get(event.data.tool_call_id)
          if (tc) {
            tc.status = 'completed'
            tc.result = event.data.result
            tc.duration_ms = event.data.duration_ms
          }
          return { ...prev, toolCalls: newToolCalls }
        })
        break

      case 'response_chunk':
        setState(prev => ({
          ...prev,
          response: prev.response + event.data.content
        }))
        break

      case 'session_end':
        options.onSessionEnd?.(event.data)
        break

      case 'error':
        options.onError?.(event.data)
        break
    }
  }, [options])

  const cancel = useCallback(() => {
    abortControllerRef.current?.abort()
    setState(prev => ({ ...prev, isStreaming: false }))
  }, [])

  return {
    ...state,
    sendMessage,
    cancel,
    toolCallsArray: Array.from(state.toolCalls.values())
  }
}
```

---

## 13. 风险和注意事项

1. **Token 消耗**：Agent 模式会消耗更多 token，需要考虑成本
2. **响应延迟**：多步推理可能导致响应变慢，需要良好的流式反馈
3. **错误处理**：工具调用可能失败，需要优雅处理
4. **无限循环**：需要设置最大步骤数防止死循环
5. **上下文长度**：多轮工具调用可能超出上下文限制，使用 SummarizationMiddleware 管理
6. **LangChain 版本兼容**：需要锁定 LangChain 版本，避免 API 变更

---

## 14. 开发阶段计划（更新版）

### Phase 1: 基础架构 (3-4天)
- [ ] 创建 `backend/agents/` 模块结构
- [ ] 定义所有 Pydantic 模型 (`models/agent_schemas.py`)
- [ ] 创建数据库表和迁移
- [ ] 实现 LangChain 兼容的工具基类
- [ ] 安装 LangChain 依赖

### Phase 2: 工具实现 (3-4天)
- [ ] 实现 search_episodic_memory (LangChain 兼容)
- [ ] 实现 search_semantic_memory
- [ ] 实现 keyword_search
- [ ] 实现 time_filter
- [ ] 实现 get_user_profile
- [ ] 实现 get_recent_activity
- [ ] 编写工具单元测试

### Phase 3: Agent 执行引擎 (3-4天)
- [ ] 实现 AgentExecutor 核心循环
- [ ] 实现 SummarizationMiddleware
- [ ] 实现模型适配器
- [ ] 实现流式事件生成器

### Phase 4: API 层 (2-3天)
- [ ] 实现 `/api/agent/chat` SSE 端点
- [ ] 实现会话管理 API
- [ ] 实现工具列表 API
- [ ] 添加错误处理和重试机制
- [ ] 编写 API 测试

### Phase 5: 前端实现 (4-5天)
- [ ] 重构 ChatPage 支持模式切换
- [ ] 优化消息样式（参考 Claude/MineContext）
- [ ] 实现 useAgentStream Hook
- [ ] 实现 ThinkingBlock 组件
- [ ] 实现 ToolCallBlock 组件
- [ ] 实现 ModeToggle 组件
- [ ] 更新 Markdown 渲染样式

### Phase 6: 集成测试和优化 (2-3天)
- [ ] 端到端测试
- [ ] 性能优化
- [ ] 用户体验优化
- [ ] 文档更新
