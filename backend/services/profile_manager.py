"""
Profile Manager - 管理用户 Profile 文件系统

Profile 使用 Markdown 文件存储用户的高阶知识，采用渐进式披露结构：
- YAML Front Matter: 元数据（title, summary, keywords, confidence）
- Summary: 1-3 句话概述
- Key Points: 关键要点列表
- Details: 详细内容
- Evidence: 证据来源
"""

import os
import re
import json
import asyncio
import aiofiles
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from enum import Enum

from config.settings import settings


@dataclass
class ProfileFile:
    """Profile 文件信息"""
    name: str
    path: str
    relative_path: str
    title: str
    summary: str
    keywords: List[str]
    confidence: float
    updated_at: Optional[datetime]
    size: int
    layer: int  # 文件所属层级 (0-5)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "path": self.path,
            "relative_path": self.relative_path,
            "title": self.title,
            "summary": self.summary,
            "keywords": self.keywords,
            "confidence": self.confidence,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "size": self.size,
            "layer": self.layer
        }


@dataclass
class SearchMatch:
    """搜索匹配结果"""
    line_number: int
    line_content: str
    context: str  # 上下文


@dataclass
class SearchResult:
    """搜索结果"""
    filename: str
    matches: List[SearchMatch]
    total_matches: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "filename": self.filename,
            "matches": [
                {
                    "line_number": m.line_number,
                    "line_content": m.line_content,
                    "context": m.context
                }
                for m in self.matches
            ],
            "total_matches": self.total_matches
        }


@dataclass
class ProfileSummary:
    """Profile 概览"""
    total_files: int
    last_updated: Optional[datetime]
    categories: Dict[str, int]  # 每个层级的文件数
    recent_changes: List[Dict[str, Any]]
    key_facts: List[str]  # 从各文件提取的关键信息

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_files": self.total_files,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
            "categories": self.categories,
            "recent_changes": self.recent_changes,
            "key_facts": self.key_facts
        }


class ProfileManager:
    """Profile 文件系统管理器"""

    _instance: Optional["ProfileManager"] = None
    _lock = asyncio.Lock()

    # 核心文件定义（按层级组织）
    CORE_FILES = {
        # 第一层：基础档案
        '00-basic-info.md': ('基本信息', 0),
        '01-core-identity.md': ('核心身份', 0),
        # 第二层：内在特质
        '10-personality.md': ('性格特质', 1),
        '11-values-beliefs.md': ('价值观与信念', 1),
        '12-cognitive-style.md': ('认知风格', 1),
        # 第三层：能力与发展
        '20-skills.md': ('技能能力', 2),
        '21-knowledge.md': ('知识领域', 2),
        '22-goals.md': ('目标愿望', 2),
        '23-interests.md': ('兴趣爱好', 2),
        # 第四层：生活方式
        '30-daily-patterns.md': ('日常模式', 3),
        '31-preferences.md': ('偏好设置', 3),
        '32-health-wellness.md': ('健康状态', 3),
        # 第五层：社会关系
        '40-relationships.md': ('人际关系', 4),
        '41-projects.md': ('项目事业', 4),
        '42-social-context.md': ('社会背景', 4),
        # 第六层：记忆与洞察
        '50-key-memories.md': ('重要记忆', 5),
        '51-patterns-insights.md': ('模式洞察', 5),
    }

    SYSTEM_FILES = ['_index.md', '_changelog.md']

    LAYER_NAMES = {
        0: '基础档案',
        1: '内在特质',
        2: '能力与发展',
        3: '生活方式',
        4: '社会关系',
        5: '记忆与洞察',
        6: '专题深入'
    }

    def __init__(self, profile_dir: Optional[Path] = None):
        if profile_dir:
            self.profile_dir = profile_dir
        else:
            # 默认使用 data 目录下的 profile
            self.profile_dir = Path(settings.data_dir) / "profile"

        self.profile_dir.mkdir(parents=True, exist_ok=True)
        self._initialized = False

    @classmethod
    def get_instance(cls) -> "ProfileManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def initialize(self) -> None:
        """初始化 Profile 目录，创建核心文件"""
        if self._initialized:
            return

        async with self._lock:
            if self._initialized:
                return

            # 创建 topics 目录
            topics_dir = self.profile_dir / "topics"
            topics_dir.mkdir(exist_ok=True)

            # 创建系统文件
            await self._ensure_file('_index.md', self._get_index_template())
            await self._ensure_file('_changelog.md', self._get_changelog_template())

            # 创建核心文件
            for filename, (title, layer) in self.CORE_FILES.items():
                template = self._get_file_template(filename, title, layer)
                await self._ensure_file(filename, template)

            self._initialized = True
            print(f"ProfileManager initialized at {self.profile_dir}")

    async def _ensure_file(self, filename: str, content: str) -> None:
        """确保文件存在，不存在则创建"""
        filepath = self.profile_dir / filename
        if not filepath.exists():
            async with aiofiles.open(filepath, 'w', encoding='utf-8') as f:
                await f.write(content)

    async def list_files(self, include_topics: bool = True) -> List[ProfileFile]:
        """列出所有 Profile 文件"""
        await self.initialize()

        files = []

        # 列出根目录文件
        for path in self.profile_dir.glob("*.md"):
            file_info = await self._get_file_info(path)
            if file_info:
                files.append(file_info)

        # 列出 topics 目录文件
        if include_topics:
            topics_dir = self.profile_dir / "topics"
            if topics_dir.exists():
                for path in topics_dir.glob("*.md"):
                    file_info = await self._get_file_info(path, "topics/")
                    if file_info:
                        files.append(file_info)

        # 按层级和文件名排序
        files.sort(key=lambda f: (f.layer, f.name))
        return files

    async def _get_file_info(self, path: Path, prefix: str = "") -> Optional[ProfileFile]:
        """获取文件信息"""
        try:
            stat = path.stat()
            content = await self.read_file(prefix + path.name)

            # 解析 YAML front matter
            metadata = self._parse_yaml_front_matter(content)

            # 确定层级
            filename = path.name
            if filename in self.CORE_FILES:
                layer = self.CORE_FILES[filename][1]
            elif prefix == "topics/":
                layer = 6
            else:
                layer = -1  # 系统文件

            return ProfileFile(
                name=path.name,
                path=str(path),
                relative_path=prefix + path.name,
                title=metadata.get('title', path.stem),
                summary=metadata.get('summary', ''),
                keywords=metadata.get('keywords', []),
                confidence=metadata.get('confidence', 0.5),
                updated_at=self._parse_date(metadata.get('updated_at')),
                size=stat.st_size,
                layer=layer
            )
        except Exception as e:
            print(f"Error getting file info for {path}: {e}")
            return None

    def _parse_yaml_front_matter(self, content: str) -> Dict[str, Any]:
        """解析 YAML front matter"""
        pattern = r'^---\s*\n(.*?)\n---\s*\n'
        match = re.match(pattern, content, re.DOTALL)

        if not match:
            return {}

        yaml_content = match.group(1)
        metadata = {}

        # 简单解析 YAML（不依赖 pyyaml）
        for line in yaml_content.split('\n'):
            line = line.strip()
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip()
                value = value.strip()

                # 处理不同类型
                if value.startswith('[') and value.endswith(']'):
                    # 列表
                    items = value[1:-1].split(',')
                    metadata[key] = [item.strip().strip('"\'') for item in items if item.strip()]
                elif value.startswith('"') and value.endswith('"'):
                    metadata[key] = value[1:-1]
                elif value.replace('.', '').isdigit():
                    metadata[key] = float(value) if '.' in value else int(value)
                else:
                    metadata[key] = value.strip('"\'')

        return metadata

    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """解析日期字符串"""
        if not date_str:
            return None
        try:
            return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        except:
            try:
                return datetime.strptime(date_str, '%Y-%m-%d')
            except:
                return None

    async def read_file(self, filename: str) -> str:
        """读取文件内容"""
        await self.initialize()

        filepath = self.profile_dir / filename
        if not filepath.exists():
            raise FileNotFoundError(f"Profile file not found: {filename}")

        async with aiofiles.open(filepath, 'r', encoding='utf-8') as f:
            return await f.read()

    async def write_file(self, filename: str, content: str, changelog_entry: str) -> None:
        """写入文件并记录变更"""
        await self.initialize()

        filepath = self.profile_dir / filename

        # 确保父目录存在
        filepath.parent.mkdir(parents=True, exist_ok=True)

        # 更新 YAML front matter 中的 updated_at
        content = self._update_yaml_timestamp(content)

        # 写入文件
        async with aiofiles.open(filepath, 'w', encoding='utf-8') as f:
            await f.write(content)

        # 记录到 changelog
        await self._add_changelog_entry(filename, changelog_entry)

        # 更新索引
        await self._update_index()

    def _update_yaml_timestamp(self, content: str) -> str:
        """更新 YAML front matter 中的时间戳"""
        now = datetime.now().strftime('%Y-%m-%d')

        # 检查是否有 YAML front matter
        pattern = r'^---\s*\n(.*?)\n---\s*\n'
        match = re.match(pattern, content, re.DOTALL)

        if match:
            yaml_content = match.group(1)
            # 更新或添加 updated_at
            if 'updated_at:' in yaml_content:
                yaml_content = re.sub(
                    r'updated_at:\s*"?[^"\n]*"?',
                    f'updated_at: "{now}"',
                    yaml_content
                )
            else:
                yaml_content += f'\nupdated_at: "{now}"'

            content = f'---\n{yaml_content}\n---\n' + content[match.end():]

        return content

    async def create_file(
        self,
        filename: str,
        title: str,
        description: str,
        initial_content: Optional[str] = None
    ) -> None:
        """创建新文件"""
        await self.initialize()

        filepath = self.profile_dir / filename

        if filepath.exists():
            raise FileExistsError(f"File already exists: {filename}")

        # 确保父目录存在
        filepath.parent.mkdir(parents=True, exist_ok=True)

        # 生成内容
        if initial_content:
            content = initial_content
        else:
            # 确定层级
            layer = 6 if filename.startswith('topics/') else -1
            content = self._get_file_template(filename, title, layer)

        # 写入文件
        async with aiofiles.open(filepath, 'w', encoding='utf-8') as f:
            await f.write(content)

        # 记录创建
        await self._add_changelog_entry(filename, f"创建新文件: {title}")

        # 更新索引
        await self._update_index()

    async def delete_file(self, filename: str) -> bool:
        """删除文件（仅允许删除 topics 中的文件）"""
        if filename in self.SYSTEM_FILES:
            raise PermissionError(f"Cannot delete system file: {filename}")

        if filename in self.CORE_FILES:
            raise PermissionError(f"Cannot delete core file: {filename}")

        filepath = self.profile_dir / filename
        if filepath.exists():
            filepath.unlink()
            await self._add_changelog_entry(filename, "删除文件")
            await self._update_index()
            return True
        return False

    async def search(self, query: str, filenames: Optional[List[str]] = None) -> List[SearchResult]:
        """搜索文件内容"""
        await self.initialize()

        results = []

        files = await self.list_files()
        files_to_search = [f.relative_path for f in files]

        if filenames:
            files_to_search = [f for f in files_to_search if f in filenames]

        for filename in files_to_search:
            try:
                content = await self.read_file(filename)
                matches = self._find_matches(content, query)
                if matches:
                    results.append(SearchResult(
                        filename=filename,
                        matches=matches,
                        total_matches=len(matches)
                    ))
            except FileNotFoundError:
                continue

        return results

    def _find_matches(self, content: str, query: str) -> List[SearchMatch]:
        """在内容中查找匹配"""
        matches = []
        query_lower = query.lower()
        lines = content.split('\n')

        for i, line in enumerate(lines):
            if query_lower in line.lower():
                # 获取上下文（前后各1行）
                start = max(0, i - 1)
                end = min(len(lines), i + 2)
                context = '\n'.join(lines[start:end])

                matches.append(SearchMatch(
                    line_number=i + 1,
                    line_content=line,
                    context=context
                ))

        return matches

    async def get_summary(self) -> ProfileSummary:
        """获取 Profile 概览"""
        await self.initialize()

        files = await self.list_files()

        # 统计各层级文件数
        categories = {}
        for layer_id, layer_name in self.LAYER_NAMES.items():
            count = len([f for f in files if f.layer == layer_id])
            if count > 0:
                categories[layer_name] = count

        # 找最近更新时间
        last_updated = None
        for f in files:
            if f.updated_at:
                if last_updated is None or f.updated_at > last_updated:
                    last_updated = f.updated_at

        # 获取最近变更
        recent_changes = await self._get_recent_changes(5)

        # 提取关键事实（从各文件的 summary）
        key_facts = []
        for f in files:
            if f.summary and f.layer >= 0:  # 排除系统文件
                key_facts.append(f"{f.title}: {f.summary}")

        return ProfileSummary(
            total_files=len(files),
            last_updated=last_updated,
            categories=categories,
            recent_changes=recent_changes,
            key_facts=key_facts[:10]  # 最多10条
        )

    async def _get_recent_changes(self, limit: int = 5) -> List[Dict[str, Any]]:
        """获取最近的变更记录"""
        try:
            content = await self.read_file('_changelog.md')

            # 解析 changelog 表格
            changes = []
            lines = content.split('\n')

            for line in lines:
                if line.startswith('|') and not line.startswith('| 日期') and '---' not in line:
                    parts = [p.strip() for p in line.split('|')[1:-1]]
                    if len(parts) >= 3:
                        changes.append({
                            'date': parts[0],
                            'filename': parts[1],
                            'description': parts[2]
                        })

            return changes[-limit:][::-1]  # 最近的在前
        except:
            return []

    async def _add_changelog_entry(self, filename: str, entry: str) -> None:
        """添加变更日志"""
        changelog_path = self.profile_dir / "_changelog.md"

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        new_entry = f"| {timestamp} | {filename} | {entry} |\n"

        try:
            async with aiofiles.open(changelog_path, 'a', encoding='utf-8') as f:
                await f.write(new_entry)
        except Exception as e:
            print(f"Error adding changelog entry: {e}")

    async def _update_index(self) -> None:
        """更新索引文件"""
        try:
            files = await self.list_files()

            # 按层级分组
            layers: Dict[int, List[ProfileFile]] = {}
            for f in files:
                if f.layer >= 0:  # 排除系统文件
                    if f.layer not in layers:
                        layers[f.layer] = []
                    layers[f.layer].append(f)

            # 生成索引内容
            now = datetime.now().strftime('%Y-%m-%d %H:%M')
            content = f'''---
title: "User Profile Index"
summary: "用户档案索引，列出所有 Profile 文件及其摘要，便于快速导航和理解用户全貌"
updated_at: "{now}"
---

# User Profile Index

## Quick Overview

> 通过阅读各文件的 summary，快速了解用户全貌

'''
            # 生成各层级表格
            for layer_id in sorted(layers.keys()):
                layer_name = self.LAYER_NAMES.get(layer_id, f"Layer {layer_id}")
                layer_files = layers[layer_id]

                content += f"### {layer_name}\n"
                content += "| 文件 | 摘要 | 置信度 | 更新时间 |\n"
                content += "|------|------|--------|--------|\n"

                for f in layer_files:
                    summary = f.summary[:60] + "..." if len(f.summary) > 60 else f.summary
                    date = f.updated_at.strftime('%Y-%m-%d') if f.updated_at else '-'
                    content += f"| [{f.name}](./{f.relative_path}) | {summary} | {f.confidence:.0%} | {date} |\n"

                content += "\n"

            content += '''---

*此索引由 Nemori Agent 自动维护，每次文件更新后同步更新*
'''
            # 写入索引
            index_path = self.profile_dir / "_index.md"
            async with aiofiles.open(index_path, 'w', encoding='utf-8') as f:
                await f.write(content)

        except Exception as e:
            print(f"Error updating index: {e}")

    # ==================== 模板方法 ====================

    def _get_index_template(self) -> str:
        """获取索引文件模板"""
        now = datetime.now().strftime('%Y-%m-%d')
        return f'''---
title: "User Profile Index"
summary: "用户档案索引，列出所有 Profile 文件及其摘要，便于快速导航和理解用户全貌"
updated_at: "{now}"
---

# User Profile Index

## Quick Overview

> 通过阅读各文件的 summary，快速了解用户全貌

*索引将在文件更新后自动生成*

---

*此索引由 Nemori Agent 自动维护*
'''

    def _get_changelog_template(self) -> str:
        """获取变更日志模板"""
        now = datetime.now().strftime('%Y-%m-%d')
        return f'''---
title: "Profile Changelog"
summary: "记录所有 Profile 文件的变更历史"
updated_at: "{now}"
---

# Profile Changelog

> 记录 Profile 文件的所有变更

| 日期 | 文件 | 变更描述 |
|------|------|---------|
| {now} | _changelog.md | 初始化变更日志 |
'''

    def _get_file_template(self, filename: str, title: str, layer: int) -> str:
        """获取文件模板"""
        now = datetime.now().strftime('%Y-%m-%d')

        # 根据文件名生成不同的模板
        templates = {
            '00-basic-info.md': self._get_basic_info_template,
            '10-personality.md': self._get_personality_template,
            '11-values-beliefs.md': self._get_values_template,
            '12-cognitive-style.md': self._get_cognitive_template,
            '20-skills.md': self._get_skills_template,
            '22-goals.md': self._get_goals_template,
            '23-interests.md': self._get_interests_template,
            '30-daily-patterns.md': self._get_daily_patterns_template,
        }

        if filename in templates:
            return templates[filename]()

        # 默认模板
        layer_desc = self.LAYER_NAMES.get(layer, "用户档案")
        return f'''---
title: "{title}"
summary: "待填充：关于用户的{title}信息"
keywords: []
confidence: 0.0
updated_at: "{now}"
---

# {title}

## Summary

> **一句话概述**：待 Agent 填充

## Key Points

- **要点1**：待填充
- **要点2**：待填充

---

## Details

*待 Agent 根据用户活动填充详细内容*

---

## Evidence

| 日期 | 观察/来源 | 置信度 |
|------|----------|--------|
| | | |

---

*此文件由 Nemori Agent 维护*
'''

    def _get_basic_info_template(self) -> str:
        now = datetime.now().strftime('%Y-%m-%d')
        return f'''---
title: "Basic Information"
summary: "待填充：用户的基础身份信息"
keywords: [身份, 基本信息, 职业, 位置]
confidence: 0.0
updated_at: "{now}"
---

# Basic Information

## Summary

> **一句话概述**：待 Agent 根据用户信息填充

## Key Points

- **称呼**：未知
- **职业**：未知
- **所在地**：未知
- **主要语言**：未知
- **时区**：未知

---

## Details

### 身份信息

- **全名/昵称**：
- **年龄段**：
- **职业类型**：
- **行业领域**：

### 联系偏好

- **活跃时间**：
- **交流风格**：

---

## Evidence

| 日期 | 来源 | 信息 |
|------|------|------|
| | | |

---

*此文件由 Nemori Agent 维护*
'''

    def _get_personality_template(self) -> str:
        now = datetime.now().strftime('%Y-%m-%d')
        return f'''---
title: "Personality Profile"
summary: "待填充：用户的性格特质分析"
keywords: [性格, 特质, 思维方式, 行为模式]
confidence: 0.0
updated_at: "{now}"
related_files: [11-values-beliefs.md, 12-cognitive-style.md]
---

# Personality Profile

## Summary

> **一句话概述**：待 Agent 观察后填充

## Key Points

- **核心特质**：待观察
- **社交倾向**：待观察
- **思维偏好**：待观察
- **情绪特点**：待观察
- **能量来源**：待观察

---

## Details

### 性格维度分析

*待 Agent 根据用户行为填充*

### 行为模式

- 在压力下：待观察
- 在舒适区：待观察
- 面对新事物：待观察

---

## Evidence

| 日期 | 观察 | 支持的特质 | 置信度 |
|------|------|-----------|--------|
| | | | |

---

*此文件由 Nemori Agent 维护*
'''

    def _get_values_template(self) -> str:
        now = datetime.now().strftime('%Y-%m-%d')
        return f'''---
title: "Values & Beliefs"
summary: "待填充：用户的价值观与信念体系"
keywords: [价值观, 信念, 原则, 人生哲学]
confidence: 0.0
updated_at: "{now}"
related_files: [10-personality.md, 22-goals.md]
---

# Values & Beliefs

## Summary

> **一句话概述**：待 Agent 观察后填充

## Key Points

- **核心价值 Top 3**：待观察
- **人生哲学**：待观察
- **行事原则**：待观察
- **看重什么**：待观察
- **避免什么**：待观察

---

## Details

### 核心价值观

*待 Agent 根据用户行为和言论填充*

### 信念系统

- **关于工作**：待观察
- **关于成长**：待观察
- **关于关系**：待观察
- **关于人生**：待观察

### 原则与底线

- **会做的**：
- **不会做的**：
- **取舍标准**：

---

## Evidence

| 日期 | 来源 | 体现的价值/信念 |
|------|------|----------------|
| | | |

---

*此文件由 Nemori Agent 维护*
'''

    def _get_cognitive_template(self) -> str:
        now = datetime.now().strftime('%Y-%m-%d')
        return f'''---
title: "Cognitive Style"
summary: "待填充：用户的认知风格和学习方式"
keywords: [认知风格, 学习方式, 决策模式, 思考习惯]
confidence: 0.0
updated_at: "{now}"
related_files: [10-personality.md, 20-skills.md]
---

# Cognitive Style

## Summary

> **一句话概述**：待 Agent 观察后填充

## Key Points

- **学习方式**：待观察
- **决策风格**：待观察
- **思维优势**：待观察
- **信息处理**：待观察
- **注意力特点**：待观察

---

## Details

### 学习偏好

- **最有效的学习方式**：
- **学习节奏**：
- **反馈偏好**：
- **学习环境**：

### 思考模式

- **分析问题**：
- **生成想法**：
- **处理复杂性**：

### 决策模式

- **信息收集**：
- **风险偏好**：
- **决策速度**：

### 注意力与精力

- **专注时长**：
- **精力高峰**：
- **恢复方式**：

---

## Evidence

| 日期 | 观察 | 认知特点 |
|------|------|---------|
| | | |

---

*此文件由 Nemori Agent 维护*
'''

    def _get_skills_template(self) -> str:
        now = datetime.now().strftime('%Y-%m-%d')
        return f'''---
title: "Skills & Abilities"
summary: "待填充：用户的技能和能力概览"
keywords: [技能, 能力, 专业, 熟练度]
confidence: 0.0
updated_at: "{now}"
related_files: [21-knowledge.md, 41-projects.md]
---

# Skills & Abilities

## Summary

> **一句话概述**：待 Agent 观察后填充

## Key Points

- **顶级技能 (精通)**：待观察
- **熟练技能**：待观察
- **正在提升**：待观察
- **想要学习**：待观察
- **技能方向**：待观察

---

## Details

### 技能矩阵

| 技能 | 水平 | 使用频率 | 最近活跃 | 成长趋势 |
|------|------|---------|---------|---------|
| | | | | |

### 技能详情

*待 Agent 根据用户活动填充*

### 技能成长

#### 正在学习

*待填充*

#### 计划学习

*待填充*

---

## Evidence

| 日期 | 技能 | 证据 | 水平评估 |
|------|------|------|---------|
| | | | |

---

*此文件由 Nemori Agent 维护*
'''

    def _get_goals_template(self) -> str:
        now = datetime.now().strftime('%Y-%m-%d')
        return f'''---
title: "Goals & Aspirations"
summary: "待填充：用户的目标和愿望"
keywords: [目标, 愿望, 规划, 追求]
confidence: 0.0
updated_at: "{now}"
related_files: [11-values-beliefs.md, 41-projects.md]
---

# Goals & Aspirations

## Summary

> **一句话概述**：待 Agent 观察后填充

## Key Points

- **长期目标**：待观察
- **中期目标**：待观察
- **短期目标**：待观察
- **主要追求**：待观察

---

## Details

### 长期目标 (1年+)

#### 职业目标

*待填充*

#### 个人成长目标

*待填充*

### 中期目标 (1-6个月)

*待填充*

### 短期目标 (本周/本月)

*待填充*

### 已实现的目标

*待填充*

---

## Evidence

| 日期 | 目标相关 | 来源 |
|------|---------|------|
| | | |

---

*此文件由 Nemori Agent 维护*
'''

    def _get_interests_template(self) -> str:
        now = datetime.now().strftime('%Y-%m-%d')
        return f'''---
title: "Interests & Hobbies"
summary: "待填充：用户的兴趣爱好"
keywords: [兴趣, 爱好, 关注, 热情]
confidence: 0.0
updated_at: "{now}"
related_files: [20-skills.md, 30-daily-patterns.md]
---

# Interests & Hobbies

## Summary

> **一句话概述**：待 Agent 观察后填充

## Key Points

- **核心兴趣**：待观察
- **活跃兴趣**：待观察
- **新兴兴趣**：待观察
- **休眠兴趣**：待观察
- **兴趣广度**：待观察

---

## Details

### 兴趣热度图

| 兴趣 | 热度 | 持续时间 | 投入频率 | 状态 |
|------|------|---------|---------|------|
| | | | | |

### 核心兴趣详情

*待 Agent 根据用户活动填充*

### 兴趣演变

*待填充*

---

## Evidence

| 日期 | 兴趣 | 活动/证据 |
|------|------|----------|
| | | |

---

*此文件由 Nemori Agent 维护*
'''

    def _get_daily_patterns_template(self) -> str:
        now = datetime.now().strftime('%Y-%m-%d')
        return f'''---
title: "Daily Patterns"
summary: "待填充：用户的日常模式和作息"
keywords: [作息, 习惯, 日常, 时间分配]
confidence: 0.0
updated_at: "{now}"
related_files: [31-preferences.md, 32-health-wellness.md]
---

# Daily Patterns

## Summary

> **一句话概述**：待 Agent 观察后填充

## Key Points

- **工作时段**：待观察
- **休息时段**：待观察
- **高效时段**：待观察
- **作息规律**：待观察

---

## Details

### 日常作息

#### 工作日

*待 Agent 根据活动记录分析*

#### 周末

*待填充*

### 习惯模式

#### 好习惯

*待填充*

#### 待改善

*待填充*

### 行为触发器

*Agent 发现的行为模式将记录在这里*

---

## Evidence

| 日期 | 观察 | 模式 |
|------|------|------|
| | | |

---

*此文件由 Nemori Agent 维护*
'''
