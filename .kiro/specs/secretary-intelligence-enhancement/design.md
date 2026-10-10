# Design Document: Secretary Intelligence Enhancement

## Overview

本设计文档描述了日程整理系统的秘书智能增强功能的技术实现方案。该功能旨在让系统更像一个真实的秘书，能够：
- 记住用户的社交意图和偏好
- 主动发现"顺便可做"的机会
- 提供基于历史记忆的个性化洞察
- 智能处理日程冲突并给出解决方案

### Design Philosophy

秘书的核心价值在于"主动性"和"洞察力"：
1. **主动性**：不等用户问，而是主动发现机会和问题
2. **洞察力**：不只是列出信息，而是提供有价值的建议
3. **记忆力**：记住用户说过的话，在合适的时机提醒
4. **判断力**：能够评估优先级、可行性、机会成本

### Key Improvements

相比现有实现，本设计增强了以下方面：
1. **记忆查询范围扩展**：从单一的 ConversationMemory 扩展到多源记忆（社交意图、历史事件、待办事项）
2. **关联发现优化**：增强 LLM prompt，明确"顺便可做"的场景；添加规则引擎作为补充
3. **上下文增强**：为每个事件附加来源、历史、人物关系等背景信息
4. **冲突解决升级**：不仅检测冲突，还提供多个解决方案和影响分析
5. **简报智能化**：从事件列表升级为洞察式汇报

## Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│              Refactored Secretary Service                    │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  SecretaryService (重构后的核心服务)                         │
│  ├─ Memory System (记忆系统)                                 │
│  │  ├─ Multi-source query (多源查询)                        │
│  │  ├─ Social intent extraction (社交意图提取)              │
│  │  └─ Relevance scoring (相关性评分)                       │
│  │                                                            │
│  ├─ Intelligence Engine (智能引擎)                           │
│  │  ├─ LLM-based discovery (LLM关联发现)                    │
│  │  ├─ Rule-based discovery (规则关联发现)                  │
│  │  ├─ Context enrichment (上下文增强)                      │
│  │  └─ Insight generation (洞察生成)                        │
│  │                                                            │
│  ├─ Conflict Management (冲突管理)                           │
│  │  ├─ Detection (检测)                                      │
│  │  ├─ Resolution generation (方案生成)                     │
│  │  └─ Impact analysis (影响分析)                           │
│  │                                                            │
│  └─ Presentation Layer (展示层)                              │
│     ├─ Timeline (时光轴)                                     │
│     ├─ Event Graph (事件图谱)                                │
│     └─ Daily Briefing (每日简报)                             │
│                                                               │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                      Data Layer                              │
├─────────────────────────────────────────────────────────────┤
│  Models:                                                     │
│  - CuratedEvent (保持不变)                                   │
│  - EventAssociation (保持不变)                               │
│  - ConversationMemory (保持不变)                             │
│  - SocialIntent (新增)                                       │
│  - Member (保持不变)                                         │
│  - ImportantDate (保持不变)                                  │
│  - CurationJob (保持不变)                                    │
└─────────────────────────────────────────────────────────────┘
```

### Integration Strategy

采用**彻底重构**策略，重新设计整个秘书智能系统：
1. 重构 `SecretaryCurationService`，将智能功能作为核心而非附加
2. 重新设计数据流，让记忆和关联成为一等公民
3. 优化现有 LLM prompt，让 AI 真正像秘书一样思考
4. 简化代码结构，移除冗余逻辑
5. 保持数据库 schema 向后兼容，但应用层逻辑全面升级


## Components and Interfaces

### 1. Memory Engine (记忆引擎)

负责多源记忆的查询、存储和关联。

#### 1.1 Social Intent Storage

**Purpose**: 存储用户表达的社交意图（如"下次去北京要约张三吃饭"）

**Data Model** (新增):
```python
class SocialIntent(Base):
    """社交意图模型"""
    __tablename__ = "social_intents"
    
    id = Column(UUID, primary_key=True)
    family_id = Column(UUID, nullable=False, index=True)
    user_id = Column(UUID, nullable=True)
    
    # 意图内容
    intent_type = Column(String(50), nullable=False)  # meet_person, send_gift, visit_place
    target_person_id = Column(UUID, nullable=True)  # 目标人物
    target_person_name = Column(String(200), nullable=True)
    action_description = Column(Text, nullable=False)  # "约吃饭"、"送礼物"
    
    # 触发条件
    trigger_type = Column(String(50), nullable=False)  # location, date, event
    trigger_location = Column(String(200), nullable=True)  # "北京"
    trigger_date = Column(Date, nullable=True)
    trigger_event_type = Column(String(50), nullable=True)  # "出差"、"旅行"
    
    # 元数据
    source_memory_id = Column(UUID, ForeignKey("conversation_memories.id"))
    confidence = Column(Float, default=0.8)
    status = Column(String(20), default="active")  # active, fulfilled, expired
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    fulfilled_at = Column(DateTime(timezone=True), nullable=True)
```

**Interface**:
```python
class MemoryEngine:
    async def extract_social_intent(
        self,
        memory: ConversationMemory,
    ) -> Optional[SocialIntent]:
        """从对话记忆中提取社交意图"""
        
    async def query_relevant_memories(
        self,
        family_id: UUID,
        context: Dict[str, Any],  # {location, date, person, event_type}
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        多源记忆查询，按相关性排序
        
        Sources:
        - ConversationMemory (对话记忆)
        - SocialIntent (社交意图)
        - CuratedEvent (历史事件)
        - Member interactions (人物互动记录)
        """
        
    async def check_triggered_intents(
        self,
        family_id: UUID,
        event: CuratedEvent,
    ) -> List[SocialIntent]:
        """检查事件是否触发了社交意图"""
```

#### 1.2 Memory Relevance Scoring

**Purpose**: 计算记忆与当前上下文的相关性

**Algorithm**:
```python
def calculate_relevance_score(
    memory: Dict[str, Any],
    context: Dict[str, Any],
) -> float:
    """
    相关性评分 = 地点匹配度 * 0.4 + 人物匹配度 * 0.3 + 
                时间接近度 * 0.2 + 语义相似度 * 0.1
    """
    score = 0.0
    
    # 地点匹配 (0-1)
    if context.get("location") and memory.get("location"):
        score += location_similarity(context["location"], memory["location"]) * 0.4
    
    # 人物匹配 (0-1)
    if context.get("person") and memory.get("person"):
        score += 1.0 * 0.3 if context["person"] == memory["person"] else 0.0
    
    # 时间接近度 (0-1)
    if context.get("date") and memory.get("date"):
        days_diff = abs((context["date"] - memory["date"]).days)
        score += max(0, 1 - days_diff / 365) * 0.2
    
    # 语义相似度 (0-1) - 使用 LLM embedding
    if context.get("text") and memory.get("text"):
        score += semantic_similarity(context["text"], memory["text"]) * 0.1
    
    return score
```

### 2. Association Discoverer (关联发现器)

负责发现事件之间的关联和"顺便可做"的机会。

#### 2.1 Enhanced LLM Prompt

**Current Issue**: 现有 `ASSOCIATION_SYSTEM_PROMPT` 不够强调"顺便可做"的场景

**Enhanced Prompt**:
```python
ENHANCED_ASSOCIATION_PROMPT = """你是一个经验丰富的私人秘书，负责为老板发现行程中的机会。

## 核心任务
基于老板的出行计划，发现"顺便可做"的事情，让行程更高效。

## 秘书思维模式

### 1. 记忆关联（最高优先级）
- 老板说过"下次去XX要做YY" → 这次去XX时强烈推荐
- 老板提到想见某人 → 在合适的行程中建议
- 老板说过某地有好餐厅/店铺 → 再去时提醒

### 2. 地理机会
- 出差城市 = 某人常住地 → 建议见面
- 行程路线经过某地 → 建议顺路办事
- 目的地附近有待办事项 → 建议顺便处理

### 3. 时间关联
- 出行期间有人生日 → 建议准备礼物
- 长时间未联系重要人物 → 建议这次联系
- 重要日期临近 → 结合行程给建议

### 4. 人情往来
- 上次见面时对方提到的事 → 这次跟进
- 欠人情需要回报 → 合适时机建议
- 关系维护需要 → 定期联系提醒

## 关联分类

### strongly_recommend (强烈推荐)
- 用户明确表达过的意愿
- 时间紧迫的事项（生日当天、deadline临近）
- 难得的机会（难得去的地方、难得见的人）

### convenient (顺便可做)
- 地理位置顺路
- 时间充裕可安排
- 额外成本低

### optional (可选)
- 需要专门安排时间
- 不在主要行程路线上
- 可以推迟到下次

## 质量标准

### 必须遵守
1. 每条关联必须是**具体的、可执行的建议**（如"约见张三"、"顺便买茶叶"）
2. 禁止通用提醒（如"检查证件"、"提前出发"）—— 这类最多1条
3. 关联的价值在于**发现老板没想到的机会**
4. 如果没有有价值的关联，返回空列表，不要凑数

### 输出格式
{
  "associations": [
    {
      "source_event_id": "事件ID",
      "target_id": "member_uuid或memory_uuid",
      "target_type": "person",
      "association_type": "memory",
      "title": "约见张三",
      "reason": "您上个月提到'出差北京时要找张三吃饭'，这次正好可以约",
      "priority": "strongly_recommend",
      "confidence": 0.9
    }
  ]
}
"""
```


#### 2.2 Rule-Based Association Engine

**Purpose**: 作为 LLM 的补充，确保不遗漏明显的关联

**Rules**:
```python
class RuleBasedAssociationEngine:
    """基于规则的关联发现引擎"""
    
    async def discover_associations(
        self,
        family_id: UUID,
        event: CuratedEvent,
        context: Dict[str, Any],
    ) -> List[EventAssociation]:
        """
        规则引擎发现的关联类型：
        1. 地点匹配：事件地点 = 联系人常住地
        2. 时间匹配：事件日期 = 重要日期（生日、纪念日）
        3. 社交意图匹配：事件触发了存储的社交意图
        4. 长时间未联系：超过N天未联系的重要人物
        5. 路线匹配：行程路线经过待办事项地点
        """
        associations = []
        
        # Rule 1: Location-based person matching
        if event.location:
            members = await self._find_members_in_location(
                family_id, event.location
            )
            for member in members:
                associations.append(self._create_location_association(
                    event, member, confidence=0.85
                ))
        
        # Rule 2: Date-based important date matching
        if event.normalized_start:
            important_dates = await self._find_important_dates_near(
                family_id, event.normalized_start.date(), days_range=7
            )
            for imp_date in important_dates:
                associations.append(self._create_temporal_association(
                    event, imp_date, confidence=0.9
                ))
        
        # Rule 3: Social intent matching
        triggered_intents = await self._check_triggered_intents(
            family_id, event
        )
        for intent in triggered_intents:
            associations.append(self._create_memory_association(
                event, intent, confidence=0.95
            ))
        
        # Rule 4: Long-time-no-contact detection
        if event.event_type in ["business_trip", "travel"]:
            stale_contacts = await self._find_stale_contacts(
                family_id, event.location, days_threshold=90
            )
            for contact in stale_contacts:
                associations.append(self._create_person_association(
                    event, contact, confidence=0.7
                ))
        
        return associations
```

#### 2.3 Association Confidence Calculation

**Purpose**: 计算关联的置信度，考虑多个因素

**Algorithm**:
```python
def calculate_association_confidence(
    event: CuratedEvent,
    target: Any,
    association_type: str,
) -> float:
    """
    置信度 = 基础分 * 地理因子 * 时间因子 * 重要性因子
    """
    base_score = {
        "memory": 0.9,      # 用户明确表达的意图
        "temporal": 0.85,   # 时间关联（生日等）
        "location": 0.8,    # 地点关联
        "person": 0.75,     # 人物关联
        "task": 0.7,        # 任务关联
    }.get(association_type, 0.5)
    
    # 地理因子 (0.5-1.0)
    geo_factor = 1.0
    if hasattr(target, "location") and event.location:
        distance_km = calculate_distance(event.location, target.location)
        if distance_km > 50:
            geo_factor = 0.5
        elif distance_km > 10:
            geo_factor = 0.7
    
    # 时间因子 (0.5-1.0)
    time_factor = 1.0
    if hasattr(target, "date") and event.normalized_start:
        days_diff = abs((target.date - event.normalized_start.date()).days)
        if days_diff > 7:
            time_factor = 0.5
        elif days_diff > 3:
            time_factor = 0.7
    
    # 重要性因子 (0.8-1.0)
    importance_factor = 1.0
    if hasattr(target, "importance"):
        importance_factor = 0.8 + (target.importance / 10) * 0.2
    
    return min(base_score * geo_factor * time_factor * importance_factor, 1.0)
```

### 3. Context Enricher (上下文增强器)

负责为事件添加背景信息和相关记忆。

#### 3.1 Event Context Structure

**Purpose**: 定义事件的完整上下文结构

**Data Structure**:
```python
class EventContext(BaseModel):
    """事件上下文"""
    
    # 来源信息
    source_info: Dict[str, Any] = Field(
        description="事件来源（对话ID、记忆ID、旅行计划ID）"
    )
    source_summary: str = Field(
        description="来源摘要（如：'来自1月15日与助手的对话'）"
    )
    
    # 历史关联
    historical_events: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="相关的历史事件（如：'上次去北京时的行程'）"
    )
    historical_summary: Optional[str] = Field(
        default=None,
        description="历史摘要（如：'上次去北京见了张三、李四'）"
    )
    
    # 人物关系
    related_people: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="相关人物及最近互动"
    )
    people_summary: Optional[str] = Field(
        default=None,
        description="人物摘要（如：'张三上次提到想要茶叶'）"
    )
    
    # 事件关联
    related_events: List[str] = Field(
        default_factory=list,
        description="相关事件ID（如：'这个会议是为了上次提到的项目'）"
    )
    event_chain_summary: Optional[str] = Field(
        default=None,
        description="事件链摘要"
    )
    
    # 决策支持
    priority_reason: Optional[str] = Field(
        default=None,
        description="优先级理由"
    )
    adjustability: str = Field(
        default="flexible",
        description="可调整性：hard_constraint, soft_constraint, flexible"
    )
    adjustability_reason: Optional[str] = Field(
        default=None,
        description="可调整性分析"
    )
```

#### 3.2 Context Enrichment Process

**Interface**:
```python
class ContextEnricher:
    async def enrich_event(
        self,
        event: CuratedEvent,
        family_id: UUID,
    ) -> EventContext:
        """为事件添加完整的上下文信息"""
        
        context = EventContext(source_info={})
        
        # 1. 提取来源信息
        context.source_info = await self._extract_source_info(event)
        context.source_summary = self._generate_source_summary(context.source_info)
        
        # 2. 查找历史事件
        if event.location:
            context.historical_events = await self._find_historical_events(
                family_id, event.location, limit=5
            )
            context.historical_summary = await self._generate_historical_summary(
                context.historical_events
            )
        
        # 3. 查找相关人物
        context.related_people = await self._find_related_people(
            family_id, event
        )
        context.people_summary = await self._generate_people_summary(
            context.related_people
        )
        
        # 4. 查找事件链
        context.related_events = await self._find_event_chain(event)
        context.event_chain_summary = await self._generate_event_chain_summary(
            context.related_events
        )
        
        # 5. 生成决策支持信息
        context.priority_reason = self._analyze_priority(event)
        context.adjustability = self._analyze_adjustability(event)
        context.adjustability_reason = self._explain_adjustability(
            event, context.adjustability
        )
        
        return context
```


### 4. Conflict Resolver (冲突解决器)

负责检测冲突并生成多个解决方案。

#### 4.1 Conflict Resolution Strategy

**Current Issue**: 现有实现只检测冲突，不提供解决方案

**Enhanced Strategy**:
```python
class ConflictResolver:
    async def resolve_conflict(
        self,
        event1: CuratedEvent,
        event2: CuratedEvent,
        family_id: UUID,
    ) -> List[ResolutionOption]:
        """
        生成多个冲突解决方案
        
        Returns:
            List of resolution options, sorted by recommendation score
        """
        options = []
        
        # 1. 分析可调整性
        adj1 = self._analyze_adjustability(event1)
        adj2 = self._analyze_adjustability(event2)
        
        # 2. 生成调整方案
        if adj1 == "flexible":
            options.extend(await self._generate_adjustment_options(
                event1, event2, adjust_event=event1
            ))
        
        if adj2 == "flexible":
            options.extend(await self._generate_adjustment_options(
                event1, event2, adjust_event=event2
            ))
        
        # 3. 生成取消方案（仅当两者都不是硬约束）
        if adj1 != "hard_constraint":
            options.append(self._generate_cancellation_option(event1, event2))
        if adj2 != "hard_constraint":
            options.append(self._generate_cancellation_option(event2, event1))
        
        # 4. 评分和排序
        for option in options:
            option.score = self._calculate_resolution_score(option)
        
        options.sort(key=lambda x: x.score, reverse=True)
        
        return options[:3]  # 返回前3个最佳方案
    
    def _analyze_adjustability(self, event: CuratedEvent) -> str:
        """
        分析事件的可调整性
        
        Returns:
            "hard_constraint": 硬约束（航班、会议）
            "soft_constraint": 软约束（可协商的约会）
            "flexible": 灵活（自由活动）
        """
        # 硬约束类型
        if event.event_type in ["travel", "meeting", "appointment"]:
            if event.status == "confirmed":
                return "hard_constraint"
            return "soft_constraint"
        
        # 重要日期（生日、纪念日）
        if event.event_type in ["birthday", "anniversary"]:
            return "hard_constraint"
        
        # 其他类型默认灵活
        return "flexible"
    
    async def _generate_adjustment_options(
        self,
        event1: CuratedEvent,
        event2: CuratedEvent,
        adjust_event: CuratedEvent,
    ) -> List[ResolutionOption]:
        """生成时间调整方案"""
        options = []
        anchor_event = event1 if adjust_event.id == event2.id else event2
        
        # 方案1：调整到之前
        before_time = anchor_event.normalized_start - timedelta(hours=2)
        if await self._check_no_new_conflicts(adjust_event, before_time):
            options.append(ResolutionOption(
                type="adjust_time",
                target_event_id=adjust_event.id,
                new_start_time=before_time,
                reason=f"将{adjust_event.title}调整到{anchor_event.title}之前",
                impact_analysis=await self._analyze_impact(adjust_event, before_time),
            ))
        
        # 方案2：调整到之后
        after_time = (anchor_event.normalized_end or anchor_event.normalized_start) + timedelta(hours=1)
        if await self._check_no_new_conflicts(adjust_event, after_time):
            options.append(ResolutionOption(
                type="adjust_time",
                target_event_id=adjust_event.id,
                new_start_time=after_time,
                reason=f"将{adjust_event.title}调整到{anchor_event.title}之后",
                impact_analysis=await self._analyze_impact(adjust_event, after_time),
            ))
        
        # 方案3：调整到第二天
        next_day = anchor_event.normalized_start + timedelta(days=1)
        if await self._check_no_new_conflicts(adjust_event, next_day):
            options.append(ResolutionOption(
                type="adjust_time",
                target_event_id=adjust_event.id,
                new_start_time=next_day,
                reason=f"将{adjust_event.title}推迟到第二天",
                impact_analysis=await self._analyze_impact(adjust_event, next_day),
            ))
        
        return options
    
    async def _check_no_new_conflicts(
        self,
        event: CuratedEvent,
        new_time: datetime,
    ) -> bool:
        """检查调整后是否会产生新的冲突"""
        # 创建虚拟事件
        virtual_event = CuratedEvent(
            **{**event.__dict__, "normalized_start": new_time}
        )
        
        # 检测冲突
        conflicts = await detect_conflicts(
            self.session,
            event.family_id,
            virtual_event,
            exclude_event_ids={event.id},
            read_only=True,
        )
        
        return len(conflicts) == 0
    
    async def _analyze_impact(
        self,
        event: CuratedEvent,
        new_time: datetime,
    ) -> str:
        """分析调整的影响"""
        impacts = []
        
        # 时间变化
        time_diff = new_time - event.normalized_start
        if time_diff.days > 0:
            impacts.append(f"推迟{time_diff.days}天")
        elif time_diff.total_seconds() / 3600 > 2:
            impacts.append(f"推迟{int(time_diff.total_seconds() / 3600)}小时")
        
        # 关联影响
        associations = await self._get_event_associations(event.id)
        if associations:
            impacts.append(f"影响{len(associations)}个关联事项")
        
        # 行程影响
        if event.trip_id:
            trip_events = await self._get_trip_events(event.trip_id)
            if len(trip_events) > 1:
                impacts.append(f"影响整个行程（共{len(trip_events)}个事件）")
        
        return "；".join(impacts) if impacts else "无明显影响"
```

#### 4.2 Resolution Option Model

**Data Structure**:
```python
class ResolutionOption(BaseModel):
    """冲突解决方案"""
    
    type: str = Field(
        description="方案类型：adjust_time, cancel, merge"
    )
    target_event_id: UUID = Field(
        description="需要调整的事件ID"
    )
    new_start_time: Optional[datetime] = Field(
        default=None,
        description="新的开始时间（adjust_time类型）"
    )
    reason: str = Field(
        description="调整理由"
    )
    impact_analysis: str = Field(
        description="影响分析"
    )
    score: float = Field(
        default=0.0,
        description="方案推荐分数（0-1）"
    )
```

### 5. Briefing Generator (简报生成器)

负责生成秘书式的每日简报。

#### 5.1 Briefing Structure

**Purpose**: 定义简报的结构，强调洞察而非列表

**Data Structure**:
```python
class DailyBriefing(BaseModel):
    """每日简报"""
    
    date: date = Field(description="简报日期")
    
    # 核心洞察（最重要）
    key_insights: List[str] = Field(
        default_factory=list,
        description="核心洞察（如：'今天去上海，上次您见了A、B、C，这次可能需要跟进'）"
    )
    
    # 优先事项（按重要性排序，非时间顺序）
    priority_items: List[BriefingItem] = Field(
        default_factory=list,
        description="优先事项"
    )
    
    # 机会提醒
    opportunities: List[str] = Field(
        default_factory=list,
        description="顺便可做的事情"
    )
    
    # 冲突和建议
    conflicts: List[ConflictBriefing] = Field(
        default_factory=list,
        description="冲突及解决建议"
    )
    
    # 人情往来提醒
    relationship_reminders: List[str] = Field(
        default_factory=list,
        description="人情往来提醒"
    )

class BriefingItem(BaseModel):
    """简报事项"""
    
    event_id: UUID
    title: str
    time_range: str  # "09:00-11:00"
    priority_level: str  # "critical", "high", "normal"
    priority_reason: str  # 为什么重要
    context_summary: str  # 背景摘要
    preparation_needed: Optional[str] = None  # 需要准备什么
```


#### 5.2 Briefing Generation Process

**Interface**:
```python
class BriefingGenerator:
    async def generate_daily_briefing(
        self,
        family_id: UUID,
        date: date,
    ) -> DailyBriefing:
        """生成每日简报"""
        
        briefing = DailyBriefing(date=date)
        
        # 1. 获取当天事件
        events = await self._get_events_for_date(family_id, date)
        
        # 2. 生成核心洞察
        briefing.key_insights = await self._generate_key_insights(
            family_id, events
        )
        
        # 3. 按重要性排序事件（非时间顺序）
        sorted_events = self._sort_by_importance(events)
        
        # 4. 为每个事件生成简报项
        for event in sorted_events:
            item = await self._create_briefing_item(event, family_id)
            briefing.priority_items.append(item)
        
        # 5. 发现机会
        briefing.opportunities = await self._discover_opportunities(
            family_id, events
        )
        
        # 6. 检测冲突并生成建议
        briefing.conflicts = await self._check_conflicts_with_solutions(
            family_id, events
        )
        
        # 7. 人情往来提醒
        briefing.relationship_reminders = await self._generate_relationship_reminders(
            family_id, events
        )
        
        return briefing
    
    async def _generate_key_insights(
        self,
        family_id: UUID,
        events: List[CuratedEvent],
    ) -> List[str]:
        """
        生成核心洞察（使用LLM）
        
        Example insights:
        - "今天去上海，上次您见了张三、李四，这次可能需要跟进"
        - "下周是李总生日，今天正好路过茶叶店，可以顺便买礼物"
        - "您已经3个月没见王总了，这次北京出差正好可以约"
        """
        # 收集上下文
        context = {
            "events": [self._event_to_dict(e) for e in events],
            "historical_events": await self._get_historical_events(family_id, events),
            "social_intents": await self._get_triggered_intents(family_id, events),
            "stale_contacts": await self._get_stale_contacts(family_id, events),
        }
        
        # 调用LLM生成洞察
        prompt = self._build_insight_prompt(context)
        response = await self.llm.chat(
            messages=[
                LLMMessage(role="system", content=INSIGHT_GENERATION_PROMPT),
                LLMMessage(role="user", content=prompt),
            ],
            temperature=0.3,
        )
        
        # 解析洞察
        insights = self._parse_insights(response.text)
        return insights[:3]  # 最多3条核心洞察
    
    def _sort_by_importance(
        self,
        events: List[CuratedEvent],
    ) -> List[CuratedEvent]:
        """
        按重要性排序事件
        
        排序因子：
        1. 优先级（critical > high > normal > low）
        2. 紧急性（deadline临近、时间固定）
        3. 机会成本（难得的机会）
        4. 关联数量（关联越多越重要）
        """
        def importance_score(event: CuratedEvent) -> float:
            score = 0.0
            
            # 优先级分数
            priority_scores = {
                "critical": 100,
                "high": 75,
                "normal": 50,
                "low": 25,
            }
            score += priority_scores.get(event.priority, 50)
            
            # 紧急性分数
            if event.event_type in ["travel", "meeting", "appointment"]:
                score += 30  # 时间固定的事件更紧急
            
            # 机会成本分数
            if event.event_type == "business_trip":
                score += 20  # 出差是难得的机会
            
            # 关联数量分数
            association_count = len(event.associations) if event.associations else 0
            score += min(association_count * 5, 20)
            
            return score
        
        return sorted(events, key=importance_score, reverse=True)
```

#### 5.3 Insight Generation Prompt

**LLM Prompt**:
```python
INSIGHT_GENERATION_PROMPT = """你是一个经验丰富的私人秘书，负责为老板生成每日简报的核心洞察。

## 任务
基于今天的行程和历史记忆，生成2-3条最有价值的洞察。

## 洞察类型

### 1. 历史关联洞察
- "今天去上海，上次您见了张三、李四，这次可能需要跟进"
- "这是您第3次去北京，前两次都见了王总"

### 2. 机会发现洞察
- "下周是李总生日，今天正好路过茶叶店，可以顺便买礼物"
- "您已经3个月没见王总了，这次北京出差正好可以约"

### 3. 意图提醒洞察
- "您上个月提到'下次去北京要约张三吃饭'，这次可以安排"
- "您说过想给李总送个礼物，今天有空可以准备"

### 4. 人情往来洞察
- "上次见张三时他提到想要茶叶，这次可以带上"
- "王总上次帮了大忙，这次见面可以表示感谢"

## 质量标准
1. 每条洞察必须是**具体的、可执行的**
2. 洞察应该是**老板没想到但很有价值的**
3. 避免显而易见的提醒（如"今天有会议"）
4. 如果没有有价值的洞察，返回空列表

## 输出格式
{
  "insights": [
    "今天去上海，上次您见了张三、李四，这次可能需要跟进",
    "下周是李总生日，今天正好路过茶叶店，可以顺便买礼物"
  ]
}
"""
```

## Data Models

### Enhanced Models

#### 1. CuratedEvent Enhancement

**Purpose**: 为现有 CuratedEvent 添加上下文字段（通过扩展而非修改）

**Approach**: 使用 JSON 字段存储扩展信息，保持向后兼容

```python
# 现有模型不变，通过 enrichments 字段存储扩展信息
# enrichments 结构：
{
    "context": {
        "source_summary": "来自1月15日与助手的对话",
        "historical_summary": "上次去北京见了张三、李四",
        "people_summary": "张三上次提到想要茶叶",
        "priority_reason": "重要客户会议",
        "adjustability": "soft_constraint",
        "adjustability_reason": "可以协商调整时间"
    },
    "secretary_notes": "聊得愉快，约定下次他来杭州"
}
```

#### 2. EventAssociation Enhancement

**Purpose**: 增强关联数据，添加更多元数据

```python
# 现有模型不变，通过扩展字段使用
# 新增字段已在现有模型中：
# - priority: "strongly_recommend", "convenient", "optional"
# - confidence: 0.0-1.0
# - reason: 详细理由

# 通过应用层逻辑增强：
# - 计算地理距离
# - 计算时间可行性
# - 评估机会成本
```

### New Models

#### 1. SocialIntent (已在 Memory Engine 部分定义)

#### 2. ResolutionOption (已在 Conflict Resolver 部分定义)

#### 3. DailyBriefing (已在 Briefing Generator 部分定义)


## Correctness Properties

*属性（Property）是一个特征或行为，应该在系统的所有有效执行中保持为真——本质上是关于系统应该做什么的形式化陈述。属性是人类可读规范和机器可验证正确性保证之间的桥梁。*

### Property 1: Social Intent Extraction Completeness

*For any* conversation memory containing social intent expressions (如"下次去XX要做YY"), the Memory Engine should extract and store a SocialIntent record with all required fields (trigger_type, trigger_location/date, target_person, action_description)

**Validates: Requirements 1.1**

### Property 2: Multi-Source Memory Query Completeness

*For any* memory query with context (location, person, date), the Memory Engine should return results from all available sources (ConversationMemory, SocialIntent, historical CuratedEvents) and not just a single source

**Validates: Requirements 1.2**

### Property 3: Memory Relevance Ordering

*For any* set of memories and a query context, the Memory Engine should return results ordered by relevance score (considering location match, person match, time proximity, semantic similarity), not by creation time

**Validates: Requirements 1.3, 1.4**

### Property 4: Social Intent Trigger Detection

*For any* new CuratedEvent and existing SocialIntents, the Memory Engine should automatically detect and return all triggered intents where the event matches the intent's trigger conditions

**Validates: Requirements 1.5**

### Property 5: Association Discovery Completeness

*For any* travel/business trip event, the Association Discoverer should query and discover associations from all relevant sources (contacts in that location, important dates nearby, social intents, stale contacts, tasks along the route)

**Validates: Requirements 2.1**

### Property 6: Association Confidence Calculation

*For any* discovered association, the confidence score should be calculated considering geographic distance, time feasibility, and importance, with closer/more feasible/more important associations having higher confidence

**Validates: Requirements 2.2**

### Property 7: Association Priority Classification

*For any* set of discovered associations, they should be classified into exactly one of three priority levels (strongly_recommend, convenient, optional) based on user intent explicitness, time urgency, and opportunity rarity

**Validates: Requirements 2.3**

### Property 8: Route-Based Task Discovery

*For any* event with a route/location and existing tasks, the Association Discoverer should identify tasks that are geographically along the route (within reasonable distance threshold)

**Validates: Requirements 2.4**

### Property 9: Important Date Preparation Reminder

*For any* important date (birthday, anniversary) within 7 days and an event in the same period, the Association Discoverer should create a temporal association suggesting preparation

**Validates: Requirements 2.5**

### Property 10: Stale Contact Detection

*For any* contact not interacted with for more than 90 days and an event in their location, the Association Discoverer should suggest meeting them

**Validates: Requirements 2.6**

### Property 11: Event Context Enrichment

*For any* CuratedEvent, the Context Enricher should attach source information, historical events, related people, event chain, and decision support information (priority reason, adjustability analysis)

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5**

### Property 12: Conflict Adjustability Analysis

*For any* pair of conflicting events, the Conflict Resolver should analyze and classify each event's adjustability (hard_constraint, soft_constraint, flexible) based on event type, status, and importance

**Validates: Requirements 4.1**

### Property 13: Multiple Resolution Options Generation

*For any* detected conflict, the Conflict Resolver should generate at least 2 resolution options (if feasible), each with adjustment reason and impact analysis

**Validates: Requirements 4.2**

### Property 14: Resolution Option Scoring

*For any* resolution option, the score should consider event importance, urgency, and opportunity cost, with lower-impact options scoring higher

**Validates: Requirements 4.3**

### Property 15: Cascading Conflict Detection

*For any* proposed time adjustment, the Conflict Resolver should check whether the new time would create new conflicts before recommending it

**Validates: Requirements 4.4**

### Property 16: Unresolvable Conflict Explanation

*For any* conflict that cannot be auto-resolved, the Conflict Resolver should provide a clear explanation of why and what user decision is needed

**Validates: Requirements 4.5**

### Property 17: Briefing Importance-Based Ordering

*For any* daily briefing, events should be ordered by importance score (considering priority, urgency, opportunity cost, association count) rather than chronological time

**Validates: Requirements 5.1**

### Property 18: Briefing Social Intent Reminder

*For any* daily briefing containing travel events, if there are triggered social intents, the briefing should include reminders about them

**Validates: Requirements 5.2**

### Property 19: Briefing Insight Generation

*For any* discovered opportunity (historical connection, social intent, stale contact), the briefing should present it as an insight (contextual suggestion) rather than a simple list item

**Validates: Requirements 5.3**

### Property 20: Briefing Important Date Preparation

*For any* important date within 7 days and events in the briefing period, the briefing should include preparation suggestions

**Validates: Requirements 5.4, 5.5**

### Property 21: Briefing Conflict Resolution

*For any* conflict in the briefing period, the briefing should include the conflict description AND at least one resolution suggestion

**Validates: Requirements 5.6**

### Property 22: Event Graph Layering

*For any* event graph generation, events should be classified into exactly one of four layers (core trips, must-do items, convenient opportunities, background info) based on event type and associations

**Validates: Requirements 6.1, 6.3, 6.4, 6.5**

### Property 23: Event Graph Association Display

*For any* event in the graph, clicking it should return all its associations and enriched context

**Validates: Requirements 6.6**

### Property 24: Timeline Event Grouping

*For any* set of events belonging to the same trip (same trip_id), the timeline should group them together with a trip theme label

**Validates: Requirements 7.2**

### Property 25: Timeline Dependency Display

*For any* event with related_events in its context, the timeline should include dependency relationship data

**Validates: Requirements 7.3, 7.4**

### Property 26: Timeline Conflict Highlighting

*For any* timeline containing conflicts, conflicting events should be marked with conflict indicators and resolution suggestions

**Validates: Requirements 7.5**

### Property 27: Incremental Association Computation

*For any* curation run, the Association Discoverer should only process events that are new or modified since the last run, not reprocess all events

**Validates: Requirements 8.2**

### Property 28: LLM Fallback Mechanism

*For any* LLM call failure or timeout, the system should fall back to rule-based association discovery and continue functioning

**Validates: Requirements 8.5**

### Property 29: Backward Compatibility

*For any* existing CuratedEvent or EventAssociation record, the enhanced system should be able to read and process it without errors

**Validates: Requirements 9.1, 9.3**

### Property 30: Error Isolation

*For any* failure in new intelligence features (Memory Engine, Context Enricher, etc.), the core curation functionality (event collection, deduplication, storage) should continue to work

**Validates: Requirements 9.5**

### Property 31: LLM Output Structure Validation

*For any* LLM response for association discovery or insight generation, the system should validate the output against a JSON schema and reject malformed responses

**Validates: Requirements 10.2, 10.3, 10.5**


## Error Handling

### 1. LLM Failure Handling

**Scenarios**:
- LLM API timeout
- LLM返回格式错误
- LLM返回空结果

**Strategy**:
```python
class LLMErrorHandler:
    async def call_llm_with_fallback(
        self,
        llm_func: Callable,
        fallback_func: Callable,
        *args,
        **kwargs,
    ) -> Any:
        """
        调用LLM，失败时回退到规则引擎
        """
        try:
            result = await asyncio.wait_for(
                llm_func(*args, **kwargs),
                timeout=30.0,  # 30秒超时
            )
            
            # 验证结果格式
            if not self._validate_llm_result(result):
                logger.warning("LLM result validation failed, using fallback")
                return await fallback_func(*args, **kwargs)
            
            return result
            
        except asyncio.TimeoutError:
            logger.error("LLM timeout, using fallback")
            return await fallback_func(*args, **kwargs)
            
        except Exception as e:
            logger.error(f"LLM error: {e}, using fallback")
            return await fallback_func(*args, **kwargs)
```

### 2. Data Consistency

**Scenarios**:
- 记忆数据不完整
- 事件关联丢失
- 上下文信息缺失

**Strategy**:
- 使用默认值填充缺失字段
- 记录数据质量问题到日志
- 不因数据问题阻塞核心流程

```python
def safe_get_context(event: CuratedEvent) -> EventContext:
    """安全获取事件上下文，缺失时使用默认值"""
    try:
        context = extract_context(event)
    except Exception as e:
        logger.warning(f"Failed to extract context for event {event.id}: {e}")
        context = EventContext(
            source_info={},
            source_summary="来源信息不可用",
            historical_events=[],
            related_people=[],
            related_events=[],
        )
    return context
```

### 3. Performance Degradation

**Scenarios**:
- 记忆查询过慢
- 关联发现超时
- 数据库负载过高

**Strategy**:
- 设置查询超时
- 限制结果数量
- 使用缓存减少重复查询

```python
class PerformanceGuard:
    async def query_with_timeout(
        self,
        query_func: Callable,
        timeout: float = 5.0,
        default_result: Any = None,
    ) -> Any:
        """带超时的查询，超时返回默认值"""
        try:
            return await asyncio.wait_for(
                query_func(),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            logger.warning(f"Query timeout after {timeout}s, returning default")
            return default_result
```

### 4. Migration Safety

**Scenarios**:
- 数据库schema变更
- 新字段添加
- 旧数据迁移

**Strategy**:
- 提供迁移脚本
- 支持渐进式迁移
- 保持向后兼容

```python
# Migration script example
async def migrate_add_social_intents():
    """
    添加 social_intents 表的迁移脚本
    """
    # 1. 创建新表
    await create_social_intents_table()
    
    # 2. 从现有 ConversationMemory 提取社交意图
    memories = await get_all_conversation_memories()
    for memory in memories:
        intent = await extract_social_intent(memory)
        if intent:
            await save_social_intent(intent)
    
    # 3. 验证迁移结果
    count = await count_social_intents()
    logger.info(f"Migrated {count} social intents")
```

## Testing Strategy

### Dual Testing Approach

本系统采用**单元测试**和**属性测试**相结合的策略：

- **单元测试**：验证具体示例、边缘情况、错误条件
- **属性测试**：验证通用属性在所有输入下的正确性

两者互补，共同确保系统的正确性和健壮性。

### Unit Testing Focus

单元测试应专注于：
1. **具体示例**：验证典型场景的正确行为
2. **边缘情况**：空输入、极端值、特殊字符
3. **错误处理**：LLM失败、数据库错误、超时
4. **集成点**：组件之间的接口调用

**Example**:
```python
async def test_social_intent_extraction_example():
    """测试社交意图提取的具体示例"""
    memory = ConversationMemory(
        content="下次去北京要约张三吃饭",
        family_id=test_family_id,
    )
    
    intent = await memory_engine.extract_social_intent(memory)
    
    assert intent is not None
    assert intent.intent_type == "meet_person"
    assert intent.trigger_location == "北京"
    assert intent.target_person_name == "张三"
    assert intent.action_description == "吃饭"

async def test_memory_query_empty_context():
    """测试空上下文的记忆查询（边缘情况）"""
    results = await memory_engine.query_relevant_memories(
        family_id=test_family_id,
        context={},
        limit=10,
    )
    
    # 应该返回空列表或最近的记忆
    assert isinstance(results, list)
    assert len(results) <= 10

async def test_llm_timeout_fallback():
    """测试LLM超时时的回退机制（错误处理）"""
    # Mock LLM to timeout
    with patch('llm.chat', side_effect=asyncio.TimeoutError()):
        associations = await association_discoverer.discover_associations(
            family_id=test_family_id,
            event=test_event,
            context={},
        )
        
        # 应该回退到规则引擎，仍然返回结果
        assert isinstance(associations, list)
```

### Property-Based Testing Configuration

属性测试配置：
- **测试库**：使用 `hypothesis` (Python)
- **迭代次数**：每个属性测试至少 100 次
- **标签格式**：`Feature: secretary-intelligence-enhancement, Property {N}: {property_text}`

**Example**:
```python
from hypothesis import given, strategies as st

@given(
    location=st.text(min_size=1, max_size=50),
    person_name=st.text(min_size=1, max_size=50),
    action=st.text(min_size=1, max_size=100),
)
async def test_property_1_social_intent_extraction_completeness(
    location: str,
    person_name: str,
    action: str,
):
    """
    Feature: secretary-intelligence-enhancement
    Property 1: Social Intent Extraction Completeness
    
    For any conversation memory containing social intent expressions,
    the Memory Engine should extract and store a SocialIntent record
    with all required fields.
    """
    # 构造包含社交意图的对话
    content = f"下次去{location}要{action}{person_name}"
    memory = ConversationMemory(
        content=content,
        family_id=test_family_id,
    )
    
    # 提取社交意图
    intent = await memory_engine.extract_social_intent(memory)
    
    # 验证所有必需字段都存在
    assert intent is not None
    assert intent.trigger_location is not None
    assert intent.target_person_name is not None
    assert intent.action_description is not None
    assert intent.intent_type is not None

@given(
    events=st.lists(
        st.builds(CuratedEvent, ...),
        min_size=1,
        max_size=20,
    )
)
async def test_property_17_briefing_importance_ordering(
    events: List[CuratedEvent],
):
    """
    Feature: secretary-intelligence-enhancement
    Property 17: Briefing Importance-Based Ordering
    
    For any daily briefing, events should be ordered by importance score
    rather than chronological time.
    """
    # 生成简报
    briefing = await briefing_generator.generate_daily_briefing(
        family_id=test_family_id,
        date=date.today(),
    )
    
    # 验证排序：每个事件的重要性分数应该 >= 下一个事件
    for i in range(len(briefing.priority_items) - 1):
        current_score = calculate_importance_score(briefing.priority_items[i])
        next_score = calculate_importance_score(briefing.priority_items[i + 1])
        assert current_score >= next_score
```

### Integration Testing

集成测试验证组件之间的协作：

```python
async def test_end_to_end_curation_with_intelligence():
    """端到端测试：从事件收集到智能简报生成"""
    
    # 1. 创建测试数据
    family_id = create_test_family()
    create_test_travel_plan(family_id, destination="北京")
    create_test_social_intent(family_id, location="北京", person="张三")
    create_test_member(family_id, name="张三", location="北京")
    
    # 2. 运行整理流程
    result = await curation_service.curate_family_events(
        family_id=family_id,
        date_range=(date.today(), date.today() + timedelta(days=7)),
    )
    
    # 3. 验证事件被正确整理
    assert result.events_curated > 0
    
    # 4. 验证关联被发现
    assert result.associations_created > 0
    
    # 5. 验证简报包含洞察
    briefing = await briefing_generator.generate_daily_briefing(
        family_id=family_id,
        date=date.today(),
    )
    assert len(briefing.key_insights) > 0
    assert any("张三" in insight for insight in briefing.key_insights)
```

### Performance Testing

性能测试确保系统在负载下的响应速度：

```python
async def test_memory_query_performance():
    """测试记忆查询性能"""
    # 创建大量测试数据
    for i in range(1000):
        create_test_memory(family_id, content=f"Memory {i}")
    
    # 测量查询时间
    start = time.time()
    results = await memory_engine.query_relevant_memories(
        family_id=family_id,
        context={"location": "北京"},
        limit=50,
    )
    duration = time.time() - start
    
    # 验证性能要求
    assert duration < 0.5  # 500ms以内
    assert len(results) <= 50

async def test_association_discovery_performance():
    """测试关联发现性能"""
    # 创建复杂场景
    event = create_test_event(family_id, location="北京")
    create_test_members(family_id, count=100)
    create_test_social_intents(family_id, count=50)
    
    # 测量发现时间
    start = time.time()
    associations = await association_discoverer.discover_associations(
        family_id=family_id,
        event=event,
        context={},
    )
    duration = time.time() - start
    
    # 验证性能要求
    assert duration < 5.0  # 5秒以内
```

## Implementation Notes

### Phase 1: Core Intelligence Layer (Week 1-2)

1. 实现 `MemoryEngine`
   - `SocialIntent` 模型和数据库迁移
   - 社交意图提取（LLM + 规则）
   - 多源记忆查询
   - 相关性评分算法

2. 实现 `RuleBasedAssociationEngine`
   - 地点匹配规则
   - 时间匹配规则
   - 社交意图匹配规则
   - 长时间未联系检测

### Phase 2: Enhanced Association Discovery (Week 3)

1. 优化 `Association_Discoverer`
   - 增强 LLM prompt
   - 集成规则引擎
   - 置信度计算
   - LLM失败回退机制

2. 实现 `ContextEnricher`
   - 来源信息提取
   - 历史事件查询
   - 人物关系查询
   - 决策支持信息生成

### Phase 3: Conflict Resolution & Briefing (Week 4)

1. 增强 `ConflictResolver`
   - 可调整性分析
   - 多方案生成
   - 影响分析
   - 连锁冲突检测

2. 实现 `BriefingGenerator`
   - 洞察生成（LLM）
   - 重要性排序
   - 机会发现
   - 人情往来提醒

### Phase 4: Integration & Testing (Week 5-6)

1. 集成到现有 `SecretaryCurationService`
2. 编写单元测试和属性测试
3. 性能优化和调优
4. 文档和部署


### Refactoring Philosophy

**当前问题**：
1. `_discover_associations` 方法过于简单，只是调用 LLM，没有充分利用记忆和规则
2. `_get_relevant_memories` 只查询 ConversationMemory，范围太窄
3. LLM prompt 不够强调"秘书思维"和"顺便可做"
4. 缺少上下文增强，事件展示时没有背景信息
5. 冲突检测有了，但解决方案生成不够智能
6. 简报只是事件列表，没有洞察

**重构策略**：
1. **重写记忆系统**：从单一源扩展到多源，添加社交意图提取和相关性评分
2. **重构关联发现**：LLM + 规则引擎双重保障，不再依赖单一方法
3. **新增上下文增强**：为每个事件附加完整的背景信息
4. **升级冲突解决**：从检测升级到方案生成和影响分析
5. **重写简报生成**：从列表升级到洞察式汇报
6. **简化代码结构**：移除冗余的 fallback 逻辑，统一错误处理

### Key Refactoring Points

#### 1. 重构 `_discover_associations` 方法

**Before** (current implementation):
```python
async def _discover_associations(
    self,
    family_id: UUID,
    curated_events: List[CuratedEvent],
    date_range: Tuple[date, date],
) -> List[EventAssociation]:
    # 只调用 LLM，没有规则引擎
    # 记忆查询范围有限
    # prompt 不够强调秘书思维
    ...
```

**After** (refactored):
```python
async def _discover_associations(
    self,
    family_id: UUID,
    curated_events: List[CuratedEvent],
    date_range: Tuple[date, date],
) -> List[EventAssociation]:
    """
    重构后的关联发现：LLM + 规则引擎双重保障
    """
    all_associations = []
    
    for event in curated_events:
        # 1. 规则引擎发现（快速、可靠）
        rule_associations = await self.rule_engine.discover_associations(
            family_id, event
        )
        
        # 2. LLM发现（智能、灵活）
        llm_associations = await self._llm_discover_associations(
            family_id, event, date_range
        )
        
        # 3. 合并去重
        merged = self._merge_associations(rule_associations, llm_associations)
        
        # 4. 过滤低质量关联
        filtered = self._filter_low_quality(merged)
        
        all_associations.extend(filtered)
    
    return all_associations
```

#### 2. 重构 `_get_relevant_memories` 方法

**Before**:
```python
async def _get_relevant_memories(
    self,
    family_id: UUID,
    curated_events: List[CuratedEvent],
) -> List[Dict[str, Any]]:
    # 只查询 ConversationMemory
    # 没有相关性排序
    # 查询限制太小（20条）
    ...
```

**After**:
```python
async def _get_relevant_memories(
    self,
    family_id: UUID,
    context: Dict[str, Any],  # {location, date, person, event_type}
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """
    重构后的记忆查询：多源 + 相关性排序
    """
    all_memories = []
    
    # 1. 查询对话记忆
    conversation_memories = await self._query_conversation_memories(
        family_id, context
    )
    all_memories.extend(conversation_memories)
    
    # 2. 查询社交意图
    social_intents = await self._query_social_intents(
        family_id, context
    )
    all_memories.extend(social_intents)
    
    # 3. 查询历史事件
    historical_events = await self._query_historical_events(
        family_id, context
    )
    all_memories.extend(historical_events)
    
    # 4. 计算相关性并排序
    scored_memories = [
        {
            **memory,
            "relevance_score": self._calculate_relevance(memory, context)
        }
        for memory in all_memories
    ]
    scored_memories.sort(key=lambda x: x["relevance_score"], reverse=True)
    
    return scored_memories[:limit]
```

#### 3. 重构 LLM Prompts

**Current Issues**:
- `ASSOCIATION_SYSTEM_PROMPT` 太通用，不够强调"顺便可做"
- 没有明确的秘书角色定位
- 质量要求不够严格，导致生成通用提醒

**Refactored Prompts**:
- 使用 `ENHANCED_ASSOCIATION_PROMPT`（已在设计中定义）
- 新增 `INSIGHT_GENERATION_PROMPT`（已在设计中定义）
- 新增 `SOCIAL_INTENT_EXTRACTION_PROMPT`

#### 4. 简化代码结构

**Remove**:
- 复杂的 fallback 逻辑（统一使用 `LLMErrorHandler`）
- 冗余的去重代码（统一使用 `_dedup_decomposed_events`）
- 分散的错误处理（统一使用 `PerformanceGuard`）

**Add**:
- 统一的错误处理器 `LLMErrorHandler`
- 统一的性能守护 `PerformanceGuard`
- 清晰的组件边界和接口

