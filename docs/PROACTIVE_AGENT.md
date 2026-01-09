# Proactive Agent 主动性智能体系统

## 概述

Proactive Agent 是 Nemori 的核心自主系统，它能够在无用户干预的情况下主动学习、更新用户档案、发现行为模式，并持续优化对用户的理解。

## 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        Proactive Agent                          │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │ ProactiveCore│  │WakeupManager│  │    TaskScheduler       │ │
│  │  (状态机)    │  │ (唤醒管理)  │  │    (任务调度)          │ │
│  └──────┬──────┘  └──────┬──────┘  └───────────┬─────────────┘ │
│         │                │                      │               │
│         └────────────────┼──────────────────────┘               │
│                          │                                      │
│  ┌───────────────────────┴───────────────────────────────────┐ │
│  │                    ProfileManager                          │ │
│  │                  (档案文件管理)                            │ │
│  └───────────────────────────────────────────────────────────┘ │
│                          │                                      │
│  ┌───────────────────────┴───────────────────────────────────┐ │
│  │                   AgentExecutor                            │ │
│  │               (LangChain 代理执行器)                       │ │
│  └───────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## 核心组件

### 1. ProactiveCore (状态机)

**文件位置**: `backend/proactive/core.py`

ProactiveCore 是整个系统的中央状态机，管理智能体的生命周期。

#### 状态定义

```python
class AgentState(Enum):
    SLEEPING = "sleeping"           # 休眠状态
    WAKING_UP = "waking_up"         # 唤醒中
    AWAKE = "awake"                 # 清醒待命
    WORKING = "working"             # 执行任务中
    GOING_TO_SLEEP = "going_to_sleep"  # 准备休眠
```

#### 状态转换图

```
                    ┌─────────────┐
                    │   SLEEPING  │
                    └──────┬──────┘
                           │ (触发器触发)
                           ▼
                    ┌─────────────┐
                    │  WAKING_UP  │
                    └──────┬──────┘
                           │ (初始化完成)
                           ▼
              ┌───────────────────────┐
              │        AWAKE          │◄────────────┐
              └───────────┬───────────┘             │
                          │ (有任务)                │ (任务完成)
                          ▼                         │
                    ┌─────────────┐                 │
                    │   WORKING   │─────────────────┘
                    └─────────────┘
                          │ (空闲超时)
                          ▼
                  ┌───────────────┐
                  │GOING_TO_SLEEP │
                  └───────┬───────┘
                          │
                          ▼
                    ┌─────────────┐
                    │   SLEEPING  │
                    └─────────────┘
```

#### 主循环逻辑

```python
async def _main_loop(self) -> None:
    while self._running:
        # 1. 休眠状态：检查唤醒触发器
        if self._state == AgentState.SLEEPING:
            trigger = await self._wakeup_manager.check_triggers()
            if trigger:
                await self.wake_up(trigger.reason)

        # 2. 清醒状态：检查并执行任务
        elif self._state == AgentState.AWAKE:
            task = await self._task_scheduler.get_next_task()
            if task:
                await self._execute_task(task)
            elif await self._should_sleep():
                await self.go_to_sleep("No pending tasks")

        await asyncio.sleep(1)  # 防止忙循环
```

### 2. WakeupManager (唤醒管理器)

**文件位置**: `backend/proactive/wakeup.py`

管理智能体的睡眠/唤醒周期，支持多种唤醒触发器。

#### 触发器类型

```python
class WakeupTriggerType(Enum):
    SCHEDULED = "scheduled"      # 定时触发（一次性）
    PERIODIC = "periodic"        # 周期触发（重复）
    TASK_DUE = "task_due"        # 任务到期触发
    NEW_DATA = "new_data"        # 新数据阈值触发
    USER_REQUEST = "user_request"  # 用户手动触发
    SYSTEM = "system"            # 系统事件触发
```

#### 默认唤醒计划

| 触发器 | 时间 | 优先级 | 用途 |
|--------|------|--------|------|
| Morning Wakeup | 09:00 | 7 | 早间例程 |
| Evening Wakeup | 20:00 | 7 | 晚间回顾 |
| Periodic Health Check | 每2小时 | 3 | 系统健康检查 |

#### 唤醒计划配置

```python
@dataclass
class WakeupSchedule:
    enabled: bool = True
    morning_wakeup: time = time(9, 0)   # 早间唤醒
    evening_wakeup: time = time(20, 0)  # 晚间唤醒
    active_days: List[int] = [0,1,2,3,4,5,6]  # 活动日（0=周一）
```

### 3. TaskScheduler (任务调度器)

**文件位置**: `backend/proactive/task_scheduler.py`

管理智能体的任务队列，按优先级调度执行。

#### 任务类型

```python
class TaskType(Enum):
    # 自我管理（最重要）
    SELF_REFLECTION = "self_reflection"     # 思考、分析、规划任务

    # 档案维护
    UPDATE_PROFILE = "update_profile"       # 更新档案文件
    CONSOLIDATE_KNOWLEDGE = "consolidate"   # 整理知识
    DISCOVER_PATTERNS = "discover_patterns" # 发现行为模式

    # 学习
    LEARN_FROM_HISTORY = "learn_from_history"  # 从历史中学习
    SUMMARIZE_PERIOD = "summarize_period"      # 生成时间段总结

    # 探索
    EXPLORE_TOPIC = "explore_topic"         # 深入探索主题
    FILL_KNOWLEDGE_GAP = "fill_gap"         # 填补知识空白

    # 系统
    HEALTH_CHECK = "health_check"           # 健康检查
    CLEANUP = "cleanup"                     # 清理旧数据
```

#### 自我反思任务 (Self-Reflection)

这是最重要的任务类型。智能体会：
1. **审视当前状态** - 检查档案文件状态和待执行任务
2. **分析已知信息** - 搜索记忆，发现新信息
3. **规划未来工作** - 使用 `create_task` 为自己安排任务

**自我反思时间安排**：每天 10:00, 14:00, 18:00, 22:00

**智能体可用的规划工具**：
| 工具名 | 描述 |
|--------|------|
| `create_task` | 创建新任务并添加到队列 |
| `get_pending_tasks` | 查看当前待执行任务 |
| `get_recent_task_history` | 查看最近完成的任务 |
| `get_profile_status` | 查看档案文件状态 |

#### 任务状态

```python
class TaskStatus(Enum):
    PENDING = "pending"           # 等待执行
    SCHEDULED = "scheduled"       # 已安排
    IN_PROGRESS = "in_progress"   # 执行中
    COMPLETED = "completed"       # 已完成
    FAILED = "failed"             # 执行失败
    CANCELLED = "cancelled"       # 已取消
```

#### 默认每日任务

| 任务 | 时间 | 类型 | 描述 |
|------|------|------|------|
| Morning Review | 09:30 | learn_from_history | 回顾昨天活动，更新档案 |
| Daily Summary | 20:30 | summarize_period | 总结今天活动 |
| Weekly Pattern Analysis | 周日 21:00 | discover_patterns | 分析一周行为模式 |

### 4. ProfileManager (档案管理器)

**文件位置**: `backend/services/profile_manager.py`

基于 Markdown 文件的用户档案存储系统。

#### 档案层级结构

```
~/.local/share/Nemori/profile/
├── 00-basic-info.md          # 基础信息
├── 01-core-identity.md       # 核心身份
├── 10-personality.md         # 性格特质
├── 11-values-beliefs.md      # 价值观与信念
├── 12-cognitive-style.md     # 认知风格
├── 20-skills-abilities.md    # 技能与能力
├── 21-knowledge-domains.md   # 知识领域
├── 22-goals-aspirations.md   # 目标与愿望
├── 23-interests-hobbies.md   # 兴趣爱好
├── 30-daily-patterns.md      # 日常模式
├── 31-preferences.md         # 偏好设置
├── 32-health-wellness.md     # 健康状况
├── 40-relationships.md       # 人际关系
├── 41-projects-work.md       # 项目与工作
├── 42-social-context.md      # 社会背景
├── 50-key-memories.md        # 关键记忆
├── 51-patterns-insights.md   # 行为模式与洞察
├── topics/                   # 专题文件夹
│   └── *.md                  # 深度主题文件
└── _changelog.md             # 变更日志
```

#### 层级定义

| 层级 | 名称 | 文件前缀 | 内容 |
|------|------|----------|------|
| 0 | 基础档案 | 0x | 基本信息、核心身份 |
| 1 | 内在特质 | 1x | 性格、价值观、认知风格 |
| 2 | 能力与发展 | 2x | 技能、知识、目标、兴趣 |
| 3 | 生活方式 | 3x | 日常模式、偏好、健康 |
| 4 | 社会关系 | 4x | 人际、项目、社会背景 |
| 5 | 记忆与洞察 | 5x | 关键记忆、行为模式 |
| 6 | 专题深入 | topics/ | 深度主题文件 |

#### 档案文件格式

每个档案文件使用 YAML Front Matter + Markdown 格式：

```markdown
---
title: "Basic Information"
layer: 0
keywords: ["identity", "name", "basic"]
summary: "用户的基础身份信息"
confidence: 0.8
related_files: ["01-core-identity.md"]
last_updated: "2026-01-09"
evidence:
  - source: "conversation_abc123"
    date: "2026-01-08"
    content: "用户提到自己的名字是..."
---

# Basic Information

## 个人信息

- **姓名**: [待填充]
- **年龄**: [待填充]
- **职业**: [待填充]

## 背景

[待填充：用户的基本背景信息]
```

## API 接口

### Proactive Agent API

**路由前缀**: `/api/proactive`

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/status` | 获取智能体状态 |
| POST | `/start` | 启动智能体 |
| POST | `/stop` | 停止智能体 |
| POST | `/wake` | 唤醒智能体 |
| POST | `/sleep` | 使智能体休眠 |
| GET | `/tasks` | 获取任务列表 |
| POST | `/tasks` | 创建新任务 |
| GET | `/tasks/{id}` | 获取任务详情 |
| DELETE | `/tasks/{id}` | 取消任务 |
| GET | `/tasks/history` | 获取任务历史 |
| GET | `/triggers` | 获取唤醒触发器 |
| POST | `/triggers` | 创建触发器 |
| GET | `/schedule` | 获取唤醒计划 |
| PUT | `/schedule` | 更新唤醒计划 |
| POST | `/actions/run-task` | 立即运行任务 |
| GET | `/task-types` | 获取可用任务类型 |

### Profile Files API

**路由前缀**: `/api/profile-files`

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/files` | 列出所有档案文件 |
| GET | `/files/{filename}` | 读取档案文件内容 |
| PUT | `/files/{filename}` | 更新档案文件 |
| POST | `/files/{filename}` | 创建新档案文件 |
| DELETE | `/files/{filename}` | 删除档案文件 |
| POST | `/search` | 搜索档案内容 |
| GET | `/summary` | 获取档案摘要 |
| GET | `/layers` | 获取层级信息 |
| GET | `/changelog` | 获取变更日志 |
| POST | `/initialize` | 初始化档案目录 |

## Agent Tools (代理工具)

智能体执行任务时可使用的 LangChain 工具：

### 档案工具 (Profile Tools)

| 工具名 | 描述 |
|--------|------|
| `list_profile_files` | 列出所有档案文件 |
| `read_profile` | 读取档案文件内容 |
| `write_profile` | 写入/更新档案文件 |
| `create_profile` | 创建新档案文件 |
| `search_profile` | 搜索档案内容 |
| `get_profile_summary` | 获取档案摘要 |
| `delete_profile` | 删除档案文件 |

### 记忆工具 (Memory Tools)

| 工具名 | 描述 |
|--------|------|
| `search_episodic_memory` | 搜索情景记忆 |
| `search_semantic_memory` | 搜索语义记忆 |
| `get_recent_activity` | 获取最近活动 |
| `time_filter` | 按时间过滤记忆 |

### 主动规划工具 (Proactive Tools)

这些工具仅在自我反思任务中可用，允许智能体管理自己的任务队列：

| 工具名 | 描述 |
|--------|------|
| `create_task` | 创建新任务，参数：task_type, title, description, priority, scheduled_hours_from_now, target_file |
| `get_pending_tasks` | 获取当前待执行任务列表 |
| `get_recent_task_history` | 获取最近完成的任务历史 |
| `get_profile_status` | 获取档案文件状态概览 |

**create_task 参数说明**：
- `task_type`: 任务类型（update_profile, learn_from_history, discover_patterns 等）
- `title`: 任务标题
- `description`: 详细描述
- `priority`: 优先级 1-10（1=低，10=紧急）
- `scheduled_hours_from_now`: 几小时后执行（可选，不填则立即执行）
- `target_file`: 目标档案文件（可选，用于 update_profile 任务）

## 任务执行流程

### 1. Learn from History 任务

```
┌─────────────────┐
│  开始任务       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 获取最近活动    │  ← get_recent_activity
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 搜索相关记忆    │  ← search_episodic_memory
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 识别新信息      │  ← LLM 分析
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 列出档案文件    │  ← list_profile_files
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 更新相关档案    │  ← write_profile
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  任务完成       │
└─────────────────┘
```

### 2. Discover Patterns 任务

```
1. 使用 time_filter 获取一周的活动数据
2. 分析时间模式（活跃时段）
3. 分析主题模式（关注领域）
4. 分析行为模式（工作方式）
5. 更新 51-patterns-insights.md
6. 更新 30-daily-patterns.md
```

### 3. Self-Reflection 任务（自我反思）

这是智能体最重要的任务，每4小时执行一次：

```
┌─────────────────────────┐
│ 1. 检查当前状态         │ ← get_profile_status
│    - 档案文件数量       │ ← get_pending_tasks
│    - 待执行任务         │ ← get_recent_task_history
│    - 最近完成的任务     │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ 2. 分析最近活动         │ ← get_recent_activity
│    - 用户做了什么       │ ← search_episodic_memory
│    - 有什么新信息       │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ 3. 规划任务             │ ← create_task (多次调用)
│    - 需要更新哪些档案   │
│    - 需要学习什么       │
│    - 需要探索什么主题   │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ 4. 完成反思报告         │
│    - 总结当前了解       │
│    - 列出规划的任务     │
└─────────────────────────┘
```

**智能体思考示例**：
```
"让我检查当前状态... 档案有19个文件，上次更新2小时前。
待执行任务队列里有 Morning Review。
最近用户讨论了很多 Python 编程的内容。
我应该创建一个任务来更新技能档案，
可能还需要深入探索 Python 这个主题。"

→ create_task("update_profile", "更新编程技能", ..., target_file="20-skills-abilities.md")
→ create_task("explore_topic", "深入了解用户的Python学习", ...)
```

## 前端界面

### Agent 页面组件

**文件位置**: `frontend/src/renderer/src/pages/ProactivePage.tsx`

#### 功能模块

1. **状态卡片**
   - 显示当前状态（Sleeping/Awake/Working）
   - Wake Up / Sleep 控制按钮
   - 今日完成任务数

2. **Status 标签页**
   - 下次计划操作
   - 最近状态转换历史
   - 快速操作按钮

3. **Tasks 标签页**
   - 任务队列
   - 任务历史（可点击查看详情）

4. **Profile 标签页**
   - 档案摘要
   - 按层级分组的文件列表
   - 文件查看器（支持 Markdown 渲染和代码视图切换）

## 配置选项

### 唤醒计划配置

```python
WakeupSchedule(
    enabled=True,
    morning_wakeup=time(9, 0),    # 早间唤醒时间
    evening_wakeup=time(20, 0),   # 晚间唤醒时间
    active_days=[0,1,2,3,4,5,6]   # 活动日（0=周一，6=周日）
)
```

### 任务调度配置

```python
TaskScheduler(
    max_tasks_in_queue=100,       # 队列最大任务数
    max_history_size=500,         # 历史记录最大数量
    default_task_timeout=timedelta(minutes=10)  # 默认任务超时
)
```

### 状态机配置

```python
ProactiveCore(
    max_working_duration=timedelta(minutes=30),  # 最大工作时间
    idle_timeout=timedelta(minutes=5)            # 空闲超时
)
```

## 数据库表

### proactive_agent_state

存储智能体状态。

```sql
CREATE TABLE proactive_agent_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    state TEXT NOT NULL DEFAULT 'sleeping',
    last_wakeup INTEGER,
    last_sleep INTEGER,
    tasks_completed_today INTEGER DEFAULT 0,
    last_daily_reset INTEGER,
    config TEXT,
    updated_at INTEGER
);
```

### proactive_tasks

存储任务信息。

```sql
CREATE TABLE proactive_tasks (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    priority INTEGER DEFAULT 5,
    status TEXT DEFAULT 'pending',
    scheduled_time INTEGER,
    recurring INTEGER DEFAULT 0,
    recurrence_interval INTEGER,
    target_file TEXT,
    context TEXT,
    result TEXT,
    error TEXT,
    created_at INTEGER,
    started_at INTEGER,
    completed_at INTEGER,
    execution_time_ms INTEGER
);
```

### wakeup_triggers

存储唤醒触发器。

```sql
CREATE TABLE wakeup_triggers (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    name TEXT NOT NULL,
    enabled INTEGER DEFAULT 1,
    scheduled_time INTEGER,
    interval_seconds INTEGER,
    last_triggered INTEGER,
    priority INTEGER DEFAULT 5,
    reason TEXT,
    metadata TEXT
);
```

## 使用示例

### 手动唤醒智能体

```typescript
// 前端调用
await api.wakeProactiveAgent('User requested wake up')
```

### 创建自定义任务

```typescript
await api.createProactiveTask({
    type: 'update_profile',
    title: 'Update hobbies',
    description: 'Update user hobbies based on recent conversations',
    priority: 7,
    target_file: '23-interests-hobbies.md'
})
```

### 立即运行任务

```typescript
await api.runProactiveTaskNow('learn_from_history', 'Manual learning task')
```

## 扩展开发

### 添加新任务类型

1. 在 `TaskType` 枚举中添加新类型
2. 在 `TaskScheduler._execute_task_by_type()` 中添加执行逻辑
3. 创建对应的执行方法

### 添加新唤醒触发器

1. 在 `WakeupTriggerType` 枚举中添加新类型
2. 在 `WakeupTrigger.is_due()` 中添加触发条件判断
3. 通过 API 或代码创建触发器实例

### 添加新档案层级

1. 在 `ProfileManager.LAYER_NAMES` 中添加层级
2. 在 `ProfileManager.CORE_FILES` 中添加核心文件
3. 创建对应的文件模板

## 故障排查

### 任务不执行

1. 检查智能体是否已启动（`/api/proactive/status`）
2. 确认主循环正在运行（`_running = True`）
3. 检查任务状态是否为 `pending`
4. 查看后端日志中的错误信息

### 智能体不唤醒

1. 检查唤醒触发器是否存在且启用
2. 确认当前时间在活动日范围内
3. 检查 `WakeupManager` 是否已初始化

### 档案文件无法访问

1. 确认档案目录已初始化（`/api/profile-files/initialize`）
2. 检查文件路径是否正确
3. 验证文件权限

---

*文档最后更新: 2026-01-09*
