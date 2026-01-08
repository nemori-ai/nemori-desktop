# Nemori Agent 功能设计文档

## 1. 概述

Agent 模式是 Nemori 的高级对话模式，能够利用多种记忆搜索工具进行深度和广度搜索，给出最优答案。与普通 Chat 模式相比，Agent 模式具备：

- **工具调用能力**：可以调用多种记忆搜索工具
- **多步推理**：可以进行多轮工具调用和推理
- **可视化过程**：前端实时展示思考过程和工具调用
- **LangChain 1.x 兼容**：完全兼容 LangChain 1.x 生态系统
- **上下文管理**：采用 SummarizationMiddleware 管理长对话

### 1.1 设计原则

1. **前后端完全分离**：通过 SSE 协议通信，后端不依赖前端实现
2. **LangChain 1.x 原生模式**：使用 `@tool` 装饰器和 `create_react_agent`
3. **协议完整性**：定义完整的事件类型和数据结构
4. **架构分离**：Agent 核心逻辑与 API 层解耦

### 1.2 技术栈版本

| 依赖 | 版本 | 说明 |
|-----|------|------|
| langchain | >= 1.2.0 | 核心框架 |
| langchain-core | >= 1.2.0 | 核心类型和工具 |
| langchain-openai | >= 1.1.0 | OpenAI 适配器 |
| langgraph | >= 0.5.0 | 图执行引擎 |
| chromadb | >= 1.0.0 | 向量数据库 |

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
    RUNNING = "running"       # Agent 正在执行
    COMPLETED = "completed"
    FAILED = "failed"

class AgentSession(BaseModel):
    """Agent 会话状态"""
    id: str                              # 会话 ID
    conversation_id: str                 # 关联的对话 ID
    status: AgentStatus
    current_step: int                    # 当前步骤
    max_steps: int = 10                  # 最大步骤数
    tool_calls_count: int = 0            # 工具调用计数
    created_at: int                      # 创建时间戳
    updated_at: int                      # 更新时间戳
    started_at: Optional[int] = None     # 开始执行时间
    completed_at: Optional[int] = None   # 完成时间
    duration_ms: Optional[int] = None    # 执行耗时
```

### 2.2 工具调用 (ToolCall)

```python
class ToolCallStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class ToolCall(BaseModel):
    """工具调用记录"""
    id: str                              # 工具调用 ID
    session_id: str                      # Agent 会话 ID
    step: int                            # 第几步
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
    THINKING_END = "thinking_end"

    # 工具调用事件
    TOOL_CALL_START = "tool_call_start"
    TOOL_CALL_ARGS = "tool_call_args"
    TOOL_CALL_RESULT = "tool_call_result"
    TOOL_CALL_ERROR = "tool_call_error"

    # 最终响应事件
    RESPONSE_START = "response_start"
    RESPONSE_CHUNK = "response_chunk"
    RESPONSE_END = "response_end"

    # 错误事件
    ERROR = "error"

class StreamEvent(BaseModel):
    """流式事件"""
    type: EventType
    session_id: str
    timestamp: int
    data: Dict[str, Any]                 # 事件数据
    step: Optional[int] = None           # 当前步骤
    tool_call_id: Optional[str] = None   # 关联的工具调用
```

---

## 3. 工具定义 (LangChain 1.x 原生模式)

### 3.1 工具定义方式

使用 LangChain 1.x 的 `@tool` 装饰器定义工具：

```python
# backend/agents/tools/memory_tools.py

from typing import Optional, List, Literal
from pydantic import BaseModel, Field
from langchain_core.tools import tool

class SearchEpisodicInput(BaseModel):
    """Input schema for search_episodic_memory tool"""
    query: str = Field(description="The search query to find relevant episodic memories")
    top_k: int = Field(default=5, ge=1, le=20, description="Number of results to return")

@tool("search_episodic_memory", args_schema=SearchEpisodicInput)
async def search_episodic_memory(query: str, top_k: int = 5) -> str:
    """Search through the user's episodic memories (life events, experiences, activities).

    Use this tool when you need to find specific events, experiences, or activities
    from the user's past.
    """
    # 实现...
```

### 3.2 Nemori 记忆搜索工具集 (已实现)

| 工具名称 | 描述 | 参数 |
|---------|------|------|
| `search_episodic_memory` | 语义搜索情景记忆 | query, top_k |
| `search_semantic_memory` | 语义搜索语义记忆 | query, category, top_k |
| `keyword_search` | 多关键词搜索记忆 | keywords[], memory_type, limit |
| `time_filter` | 按时间范围过滤 | start_date, end_date, days_ago, limit |
| `get_user_profile` | 获取用户画像 | categories[] |
| `get_recent_activity` | 获取最近活动 | limit |
| `search_chat_history` | 搜索原始聊天记录 | query, role, limit |

### 3.3 工具实现示例

```python
class KeywordSearchInput(BaseModel):
    """Input schema for keyword_search tool"""
    keywords: List[str] = Field(
        description="List of keywords to search for (e.g. ['meeting', 'project'])"
    )
    memory_type: Optional[Literal['episodic', 'semantic']] = Field(
        default=None,
        description="Optional: 'episodic' or 'semantic'. Omit to search both."
    )
    limit: int = Field(default=10, ge=1, le=50)

@tool("keyword_search", args_schema=KeywordSearchInput)
async def keyword_search(
    keywords: List[str],
    memory_type: Optional[str] = None,
    limit: int = 10
) -> str:
    """Search memories using keyword matching.

    Args:
        keywords: List of keywords to search for (e.g. ["meeting", "project"])
        memory_type: Optional filter - "episodic" or "semantic". Omit to search both.
        limit: Maximum number of results (default: 10)

    Returns memories containing ANY of the specified keywords.
    """
    db = Database.get_instance()
    conn = db._connection

    # Build OR conditions for multiple keywords
    conditions = " OR ".join(["content LIKE ?" for _ in keywords])
    patterns = [f"%{kw}%" for kw in keywords]

    # Query database...
    return json.dumps({"success": True, "keywords": keywords, "results": results})
```

### 3.4 工具工厂函数

```python
# backend/agents/tools/__init__.py

def get_memory_tools():
    """Get all memory search tools for the agent.

    Returns a list of tool functions decorated with @tool.
    These are compatible with LangChain 1.x's create_react_agent function.
    """
    return [
        search_episodic_memory,
        search_semantic_memory,
        keyword_search,
        time_filter,
        get_user_profile,
        get_recent_activity,
        search_chat_history,
    ]
```

---

## 4. Agent 执行引擎 (实际实现)

### 4.1 使用 LangGraph create_react_agent

```python
# backend/agents/executor.py

from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI

class AgentExecutor:
    """Executes agent conversations using LangChain 1.x native agent pattern."""

    def __init__(self, max_steps: int = 10, tools: Optional[List] = None):
        self.max_steps = max_steps
        self.tools = tools or get_all_tools()
        self.llm_service = LLMService.get_instance()
        self.middleware = SummarizationMiddleware()

    def _create_langchain_agent(self):
        """Create a LangGraph ReAct agent with our tools."""
        chat_model = ChatOpenAI(
            model=self.llm_service.model,
            api_key=self.llm_service.api_key,
            base_url=self.llm_service.base_url,
            temperature=0.7,
        ).bind(parallel_tool_calls=False)  # 禁用并行工具调用

        agent = create_react_agent(
            model=chat_model,
            tools=self.tools,
            prompt=self._build_system_prompt(),  # 使用 prompt 参数
        )

        return agent
```

### 4.2 关键设计决策

#### 4.2.1 禁用并行工具调用

```python
chat_model = ChatOpenAI(...).bind(parallel_tool_calls=False)
```

**原因**：LangGraph 在流式模式下处理并行工具调用存在已知问题，可能导致：
- 部分工具结果未返回就生成最终响应
- 工具调用状态跟踪混乱

**解决方案**：使用 `.bind(parallel_tool_calls=False)` 强制顺序执行工具。

#### 4.2.2 使用 prompt 参数而非 state_modifier

```python
agent = create_react_agent(
    model=chat_model,
    tools=self.tools,
    prompt=self._build_system_prompt(),  # 推荐方式
)
```

**原因**：`state_modifier` 在 LangGraph 中存在已知问题，`prompt` 是推荐的系统提示设置方式。

### 4.3 系统提示词

```python
AGENT_SYSTEM_PROMPT = """You are Nemori, an intelligent personal assistant with access to the user's memory system.

Current date and time: {current_datetime}

You have access to the following tools to search and retrieve information from the user's memories:

{tools_description}

When answering questions about the user or their past experiences:
1. First, use the appropriate memory search tools to find relevant information
2. Combine information from multiple sources if needed
3. Provide comprehensive answers based on the retrieved memories
4. If no relevant memories are found, let the user know

Guidelines:
- Use semantic search (search_episodic_memory, search_semantic_memory) when looking for meaning or context
- Use keyword_search when looking for specific terms or exact matches
- Use time_filter when the question involves specific time periods
- Use get_user_profile to understand the user's overall preferences
- Use search_chat_history to find specific conversations
"""
```

### 4.4 流式执行

```python
async def _stream_agent_execution(
    self,
    agent,
    messages: List,
    session: AgentSession
) -> AsyncGenerator[StreamEvent, None]:
    """Stream agent execution events."""

    async for event in agent.astream(
        {"messages": messages},
        stream_mode="values"
    ):
        latest_message = event.get("messages", [])[-1]

        # Check for tool calls
        if hasattr(latest_message, 'tool_calls') and latest_message.tool_calls:
            for tool_call in latest_message.tool_calls:
                # Emit tool_call_start, tool_call_args events
                yield StreamEvent.tool_call_start(...)

        # Check for tool results
        elif isinstance(latest_message, ToolMessage):
            # Emit tool_call_result event
            yield StreamEvent.tool_call_result(...)

        # Check for final response
        elif isinstance(latest_message, AIMessage):
            if not latest_message.tool_calls:
                # Emit response events
                yield StreamEvent.response_chunk(...)
```

---

## 5. 记忆处理集成

### 5.1 聊天消息加入记忆

用户消息和助手回复都会被加入记忆处理队列：

```python
# backend/api/routes/chat.py

# Add both user and assistant messages to memory batch
await memory.add_to_batch({
    "id": user_message_id,
    "role": "user",
    "content": request.content,
    "timestamp": timestamp,
    "conversation_id": conversation_id
})
await memory.add_to_batch({
    "id": assistant_message_id,
    "role": "assistant",
    "content": response_content,
    "timestamp": assistant_timestamp,
    "conversation_id": conversation_id
})
```

---

## 6. 持久化方案

### 6.1 数据库表设计

```sql
-- Agent 会话表
CREATE TABLE IF NOT EXISTS agent_sessions (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'idle',
    current_step INTEGER DEFAULT 0,
    max_steps INTEGER DEFAULT 10,
    config TEXT,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    started_at INTEGER,
    completed_at INTEGER,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
);

-- 工具调用记录表
CREATE TABLE IF NOT EXISTS tool_calls (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    step INTEGER NOT NULL,
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

-- 索引
CREATE INDEX IF NOT EXISTS idx_agent_sessions_conversation ON agent_sessions(conversation_id);
CREATE INDEX IF NOT EXISTS idx_tool_calls_session ON tool_calls(session_id);
```

---

## 7. 后端架构

```
backend/
├── agents/                    # Agent 核心模块
│   ├── __init__.py
│   ├── executor.py           # Agent 执行引擎 (create_react_agent)
│   ├── tools/                # 工具集
│   │   ├── __init__.py      # 工具导出和工厂函数
│   │   └── memory_tools.py  # 记忆搜索工具 (@tool 装饰器)
│   └── middleware/
│       └── summarization.py # 上下文摘要中间件
├── api/
│   └── routes/
│       └── agent.py         # Agent API 路由 (SSE)
├── models/
│   └── agent_schemas.py     # Agent 数据模型
└── services/
    └── llm_service.py       # LLM 服务 (提供 model, api_key, base_url 属性)
```

---

## 8. 技术决策总结

| 决策点 | 选择 | 理由 |
|-------|------|------|
| Agent 框架 | LangGraph create_react_agent | LangChain 1.x 官方推荐 |
| 工具定义 | @tool 装饰器 + Pydantic Schema | 类型安全、LLM 友好 |
| 并行工具调用 | 禁用 | 流式模式下存在已知问题 |
| 系统提示 | prompt 参数 | state_modifier 有兼容问题 |
| 流式协议 | SSE | 简单、兼容性好 |
| 持久化 | SQLite | 与现有系统一致 |

---

## 9. 已知问题和解决方案

### 9.1 并行工具调用问题

**问题**：LangGraph 在 stream_mode="values" 下，并行工具调用可能导致部分结果未返回就生成响应。

**解决方案**：
```python
chat_model.bind(parallel_tool_calls=False)
```

### 9.2 state_modifier 不生效

**问题**：`create_react_agent` 的 `state_modifier` 参数在某些版本中不生效。

**解决方案**：使用 `prompt` 参数设置系统提示。

### 9.3 LLMService 属性访问

**问题**：executor 需要访问 LLMService 的 model, api_key, base_url。

**解决方案**：在 LLMService 中添加公开属性：
```python
@property
def model(self) -> str:
    return self._chat_model

@property
def api_key(self) -> str:
    return self._chat_api_key

@property
def base_url(self) -> str:
    return self._chat_base_url
```

---

## 10. 开发进度

### Phase 1: 基础架构 ✅
- [x] 创建 `backend/agents/` 模块结构
- [x] 定义所有 Pydantic 模型
- [x] 创建数据库表
- [x] 安装 LangChain 1.x 依赖

### Phase 2: 工具实现 ✅
- [x] search_episodic_memory
- [x] search_semantic_memory
- [x] keyword_search (支持多关键词)
- [x] time_filter
- [x] get_user_profile
- [x] get_recent_activity
- [x] search_chat_history (新增)

### Phase 3: Agent 执行引擎 ✅
- [x] 使用 create_react_agent 实现
- [x] 实现 SummarizationMiddleware
- [x] 实现流式事件生成
- [x] 禁用并行工具调用

### Phase 4: API 层 ✅
- [x] 实现 `/api/agent/chat` SSE 端点
- [x] 实现会话管理
- [x] 错误处理

### Phase 5: 前端实现 ✅
- [x] ChatPage 支持 Agent 模式切换
- [x] 工具调用可视化
- [x] 思考过程展示
- [x] 流式响应渲染

### Phase 6: 优化 (进行中)
- [x] 禁用并行工具调用解决流式问题
- [x] 聊天消息加入记忆处理
- [ ] 性能优化
- [ ] 用户体验优化

---

## 11. 参考资源

- [LangChain 1.0 发布公告](https://changelog.langchain.com/announcements/langchain-1-0-now-generally-available)
- [LangGraph Agents Reference](https://reference.langchain.com/python/langgraph/agents/)
- [create_react_agent 并行调用问题](https://github.com/langchain-ai/langgraphjs/issues/1289)
- [ChromaDB 迁移指南](https://docs.trychroma.com/deployment/migration)
