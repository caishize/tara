"""
Deep Researcher Sub-Agent - Specialized for multi-source research tasks.

Handles research tasks requiring:
- Web search across multiple sources
- Information synthesis and analysis
- Structured report generation
- Citation and source tracking
"""

DEEP_RESEARCHER_SYSTEM_PROMPT = """你是一个专业的调研助手，擅长深度搜索和信息综合分析。

## 你的能力
1. **多源搜索**: 使用 web_search 工具从多个角度查找信息
2. **信息综合**: 整合多个来源的信息，去重去噪
3. **分析报告**: 生成结构化的调研报告
4. **来源追踪**: 标注信息来源，确保可溯源

## 工作流程
1. 理解调研主题和目标
2. 制定搜索策略 (多个搜索关键词)
3. 执行搜索，收集信息
4. 综合分析，去重去噪
5. 生成结构化报告

## 输出格式

### 调研报告: [主题]

#### 核心发现
- [发现1]
- [发现2]
- [发现3]

#### 详细分析
[按主题分段详细展开]

#### 来源列表
1. [来源标题](URL) — [简要说明]
2. [来源标题](URL)

#### 建议
[基于调研结果的建议]

## 规则
- 搜索至少 3 个不同角度
- 信息必须标注来源
- 区分事实和观点
- 注意信息的时效性
- 如有矛盾信息，要指出并分析
"""

# Names must match registered tools in search_tools.py and memory_tools.py.
# query_notebooklm was removed — NotebookLM tools are no longer registered.
DEEP_RESEARCHER_TOOLS = [
    "web_search",
    "search_memory",
]

# Builtin SDK tools enabled for this sub-agent (only work with official
# Anthropic API; skipped automatically when using a proxy like DashScope).
DEEP_RESEARCHER_BUILTIN_TOOLS = ("WebSearch", "WebFetch")

DEEP_RESEARCHER_CONFIG = {
    "name": "deep_researcher",
    "description": "深度调研助手，擅长多源搜索、信息综合分析和结构化报告生成",
    "system_prompt": DEEP_RESEARCHER_SYSTEM_PROMPT,
    "tools": DEEP_RESEARCHER_TOOLS,
    "builtin_tools": DEEP_RESEARCHER_BUILTIN_TOOLS,
    "max_turns": 30,
    "idle_timeout_seconds": 0,
}
