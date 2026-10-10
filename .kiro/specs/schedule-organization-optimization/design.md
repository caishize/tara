# Design Document: Schedule Organization Optimization

## Overview

本设计文档描述了智能秘书系统日程整理功能的优化方案。系统包含三个核心模块：事件图谱（Event Graph）、时光轴（Timeline）和简报（Daily Briefing）。优化的核心理念是"秘书思维"——优先级高于完整性，行动导向，渐进式披露，智能预判。

### Design Philosophy

1. **Single Source of Truth**: 使用 `curated_events` 作为唯一数据源
2. **Layered Information Architecture**: 按紧急程度分层，默认展示最重要信息
3. **Action-Oriented**: 每条信息都包含可执行的行动建议
4. **Proactive Intelligence**: 提前发现问题，而非被动展示

### Key Improvements

- 统一的三层紧急度分类体系（blocking/recommended/reference）
- 关联价值评分机制，过滤低价值信息
- 强制多天事件拆解，不依赖LLM
- 实时冲突检测与可视化
- 智能预警系统（天气、交通、证件）
- 每条信息都有明确的CTA（Call To Action）

## Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                     Presentation Layer                       │
├──────────────┬──────────────────┬──────────────────────────┤
│ Event Graph  │    Timeline      │    Daily Briefing        │
│   Module     │     Module       │       Module             │
└──────┬───────┴────────┬─────────┴──────────┬───────────────┘
       │                │                    │
       └────────────────┼────────────────────┘
                        │
         ┌──────────────▼──────────────┐
         │    Business Logic Layer     │
         ├─────────────────────────────┤
         │ - Association Engine        │
         │ - Value Scoring Engine      │
         │ - Trip Grouping Engine      │
         │ - Conflict Detection Engine │
         │ - Alert Generation Engine   │
         │ - Action Generator          │
         └──────────────┬──────────────┘
                        │
         ┌──────────────▼──────────────┐
         │      Data Access Layer      │
         ├─────────────────────────────┤
         │ - Curated Events Repository │
         │ - Cache Manager             │
         │ - External Calendar Sync    │
         └─────────────────────────────┘
```

### Module Responsibilities

**Event Graph Module**:
- 展示以行程为中心的关联信息
- 实现三层紧急度分类展示
- 支持分层展开/折叠
- 提供行程切换功能

**Timeline Module**:
- 按日期或行程分组展示事件
- 实时检测和标记时间冲突
- 生成智能事件标签
- 支持视图模式切换

**Daily Briefing Module**:
- 生成每日简报
- 按优先级排序信息
- 生成智能预警
- 为每条信息生成行动按钮

**Association Engine**:
- 使用LLM生成事件关联
- 计算关联价值评分
- 过滤低价值关联
- 去重相似关联

**Value Scoring Engine**:
- 评估关联的相关性（Relevance）
- 评估关联的可行动性（Actionability）
- 评估关联的具体性（Specificity）
- 计算综合价值分数

**Trip Grouping Engine**:
- 智能分组相关事件为行程
- 检测日期连续性
- 考虑地理位置邻近性
- 避免不合理的日期间隔

**Conflict Detection Engine**:
- 检测时间重叠
- 计算冲突严重程度
- 生成冲突解决建议

**Alert Generation Engine**:
- 生成天气预警
- 生成交通预警
- 生成证件提醒
- 检查航班/火车变更

**Action Generator**:
- 根据事件类型生成行动建议
- 生成可执行的CTA按钮
- 支持快速操作

## Components and Interfaces

### 1. Association Engine

```python
class AssociationEngine:
    """
    负责生成和管理事件关联
    """
    
    def generate_associations(
        self,
        event_id: str,
        context_events: List[Event]
    ) -> List[Association]:
        """
        为指定事件生成关联
        
        Args:
            event_id: 目标事件ID
            context_events: 上下文事件列表
            
        Returns:
            关联列表，已按价值评分排序
        """
        pass
    
    def calculate_value_score(
        self,
        association: Association
    ) -> float:
        """
        计算关联的价值评分
        
        Returns:
            0.0-1.0之间的评分
        """
        pass
    
    def filter_low_value_associations(
        self,
        associations: List[Association],
        threshold: float = 0.3
    ) -> List[Association]:
        """
        过滤低价值关联
        
        Args:
            associations: 关联列表
            threshold: 最低价值阈值
            
        Returns:
            过滤后的关联列表
        """
        pass
    
    def deduplicate_associations(
        self,
        associations: List[Association]
    ) -> List[Association]:
        """
        去重相似关联，保留最高价值的
        """
        pass
```

### 2. Value Scoring Engine

```python
class ValueScoringEngine:
    """
    计算关联价值评分
    """
    
    def score_relevance(self, association: Association) -> float:
        """
        评估相关性 (0.0-1.0)
        
        考虑因素：
        - 时间接近度
        - 主题相关性
        - 人物关联度
        """
        pass
    
    def score_actionability(self, association: Association) -> float:
        """
        评估可行动性 (0.0-1.0)
        
        考虑因素：
        - 是否包含具体行动项
        - 是否有明确的截止时间
        - 是否可以直接执行
        """
        pass
    
    def score_specificity(self, association: Association) -> float:
        """
        评估具体性 (0.0-1.0)
        
        考虑因素：
        - 是否包含具体细节
        - 是否避免通用描述
        - 是否有量化信息
        """
        pass
    
    def calculate_composite_score(
        self,
        relevance: float,
        actionability: float,
        specificity: float
    ) -> float:
        """
        计算综合评分
        
        权重：relevance=0.4, actionability=0.4, specificity=0.2
        """
        pass
```

### 3. Trip Grouping Engine

```python
class TripGroupingEngine:
    """
    智能分组事件为行程
    """
    
    MAX_GAP_DAYS = 2  # 最大允许间隔天数
    
    def group_events_into_trips(
        self,
        events: List[Event]
    ) -> List[Trip]:
        """
        将事件分组为行程
        
        算法：
        1. 按开始时间排序事件
        2. 检测日期连续性（间隔<=2天）
        3. 检测地理位置邻近性
        4. 合并符合条件的事件为行程
        """
        pass
    
    def check_date_continuity(
        self,
        event1: Event,
        event2: Event
    ) -> bool:
        """
        检查两个事件的日期是否连续
        
        Returns:
            True if 间隔 <= MAX_GAP_DAYS
        """
        pass
    
    def check_location_proximity(
        self,
        event1: Event,
        event2: Event
    ) -> bool:
        """
        检查两个事件的地理位置是否邻近
        
        考虑因素：
        - 同一城市
        - 同一国家/地区
        - 距离阈值
        """
        pass
    
    def validate_trip_range(self, trip: Trip) -> bool:
        """
        验证行程日期范围的合理性
        
        检查：
        - 没有超过MAX_GAP_DAYS的间隔
        - 总时长合理（不超过30天）
        """
        pass
```

### 4. Multi-Day Event Decomposer

```python
class MultiDayEventDecomposer:
    """
    强制拆解多天事件
    """
    
    def decompose_event(
        self,
        event: Event,
        user_timezone: str
    ) -> List[DailyEventEntry]:
        """
        将多天事件拆解为每日条目
        
        Args:
            event: 原始事件
            user_timezone: 用户时区
            
        Returns:
            每日事件条目列表
            
        算法：
        1. 转换到用户时区
        2. 按日期边界拆解
        3. 为每个条目生成智能标签
        4. 保留原始事件引用
        """
        pass
    
    def generate_daily_label(
        self,
        event: Event,
        day_index: int,
        total_days: int
    ) -> str:
        """
        生成每日智能标签
        
        格式示例：
        - "北京出差 第1天：抵达+客户会议"
        - "北京出差 第2天：产品演示+晚宴"
        
        而不是：
        - "Day 1 · 北京出差"
        """
        pass
    
    def handle_midnight_crossing(
        self,
        event: Event,
        timezone: str
    ) -> Tuple[Event, Event]:
        """
        处理跨午夜的事件
        
        Returns:
            拆分后的两个事件
        """
        pass
```

### 5. Conflict Detection Engine

```python
class ConflictDetectionEngine:
    """
    检测和分析时间冲突
    """
    
    def detect_conflicts(
        self,
        events: List[Event]
    ) -> List[Conflict]:
        """
        检测所有时间冲突
        
        算法：
        1. 按开始时间排序
        2. 使用扫描线算法检测重叠
        3. 计算冲突严重程度
        4. 检查冲突状态，避免重复通知
        """
        pass
    
    def calculate_conflict_severity(
        self,
        conflict: Conflict
    ) -> ConflictSeverity:
        """
        计算冲突严重程度
        
        考虑因素：
        - 事件优先级
        - 重叠时长
        - 是否可移动
        
        Returns:
            CRITICAL | HIGH | MEDIUM | LOW
        """
        pass
    
    def generate_resolution_suggestions(
        self,
        conflict: Conflict
    ) -> List[ResolutionSuggestion]:
        """
        生成冲突解决建议
        
        建议类型：
        - 重新安排时间
        - 缩短事件时长
        - 取消低优先级事件
        - 委托他人参加
        """
        pass
    
    def should_notify_conflict(
        self,
        conflict: Conflict,
        notification_cooldown: int = 24  # 小时
    ) -> bool:
        """
        判断是否应该通知用户此冲突
        
        避免重复通知的规则：
        1. 如果冲突已被用户确认（acknowledged）或解决（resolved），不通知
        2. 如果冲突已被用户忽略（dismissed），不通知
        3. 如果冲突在冷却期内已通知过，不重复通知
        4. 如果冲突的事件发生了变化（重新计算冲突ID），视为新冲突
        
        Args:
            conflict: 冲突对象
            notification_cooldown: 通知冷却期（小时）
            
        Returns:
            True if 应该通知，False otherwise
        """
        pass
    
    def calculate_conflict_id(
        self,
        event_ids: List[str],
        overlap_start: datetime,
        overlap_end: datetime
    ) -> str:
        """
        计算冲突的唯一ID
        
        基于：
        - 涉及的事件ID（排序后）
        - 重叠的开始和结束时间
        
        这样当事件时间调整后，冲突ID会改变，视为新冲突
        """
        pass
    
    def update_conflict_status(
        self,
        conflict_id: str,
        status: str,
        user_id: str
    ) -> None:
        """
        更新冲突状态
        
        状态转换：
        - pending → acknowledged: 用户已查看但未处理
        - pending → dismissed: 用户选择忽略
        - pending/acknowledged → resolved: 用户已解决（调整时间等）
        
        Args:
            conflict_id: 冲突ID
            status: 新状态
            user_id: 操作用户ID
        """
        pass
```

### 6. Alert Generation Engine

```python
class AlertGenerationEngine:
    """
    生成智能预警
    """
    
    def generate_weather_alerts(
        self,
        events: List[Event],
        date: datetime
    ) -> List[Alert]:
        """
        生成天气预警
        
        检查：
        - 户外活动遇到恶劣天气
        - 出行日期的天气状况
        """
        pass
    
    def generate_traffic_alerts(
        self,
        events: List[Event],
        date: datetime
    ) -> List[Alert]:
        """
        生成交通预警
        
        检查：
        - 高峰时段出行
        - 预计交通拥堵
        - 建议提前出发时间
        """
        pass
    
    def generate_document_reminders(
        self,
        events: List[Event],
        date: datetime
    ) -> List[Alert]:
        """
        生成证件提醒
        
        检查：
        - 需要身份证的场合
        - 需要护照的出境行程
        - 需要工作证的场合
        """
        pass
    
    def check_travel_schedule_changes(
        self,
        events: List[Event]
    ) -> List[Alert]:
        """
        检查航班/火车变更
        
        需要集成外部API：
        - 航班动态查询
        - 火车时刻表查询
        """
        pass
    
    def prioritize_alerts(
        self,
        alerts: List[Alert]
    ) -> List[Alert]:
        """
        按影响程度排序预警
        
        优先级：
        1. 航班/火车变更
        2. 证件提醒
        3. 恶劣天气
        4. 交通拥堵
        """
        pass
```

### 7. Action Generator

```python
class ActionGenerator:
    """
    生成行动建议和CTA按钮
    """
    
    def generate_actions(
        self,
        item: BriefingItem
    ) -> List[Action]:
        """
        为简报项生成行动建议
        
        根据项目类型生成：
        - 会议：导航、拨打电话、查看资料
        - 待办：标记完成、设置提醒、委托
        - 出行：导航、查看天气、检查证件
        """
        pass
    
    def prioritize_actions(
        self,
        actions: List[Action]
    ) -> List[Action]:
        """
        排序行动建议
        
        将最相关的行动设为主按钮
        """
        pass
    
    def create_quick_action(
        self,
        action_type: ActionType,
        context: Dict
    ) -> Action:
        """
        创建快速操作
        
        支持的操作类型：
        - NAVIGATE: 打开地图导航
        - CALL: 拨打电话
        - RESCHEDULE: 重新安排时间
        - MARK_DONE: 标记完成
        - DELEGATE: 委托他人
        - VIEW_DETAILS: 查看详情
        """
        pass
```

## Data Models

### Core Models

```python
from enum import Enum
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Dict

class UrgencyLevel(Enum):
    """紧急程度"""
    BLOCKING = "blocking"      # 必须处理
    RECOMMENDED = "recommended"  # 建议处理
    REFERENCE = "reference"     # 参考信息

class DataType(Enum):
    """数据类型"""
    PERSON = "person"
    TASK = "task"
    MEMORY = "memory"
    REMINDER = "reminder"
    LOCATION = "location"

class ConflictSeverity(Enum):
    """冲突严重程度"""
    CRITICAL = "critical"  # 完全重叠，高优先级
    HIGH = "high"          # 部分重叠，高优先级
    MEDIUM = "medium"      # 完全重叠，低优先级
    LOW = "low"            # 部分重叠，低优先级

class ActionType(Enum):
    """行动类型"""
    NAVIGATE = "navigate"
    CALL = "call"
    RESCHEDULE = "reschedule"
    MARK_DONE = "mark_done"
    DELEGATE = "delegate"
    VIEW_DETAILS = "view_details"

@dataclass
class Event:
    """事件"""
    id: str
    title: str
    start_time: datetime  # UTC
    end_time: datetime    # UTC
    location: Optional[str]
    description: Optional[str]
    priority: int  # 1-5
    is_all_day: bool
    timezone: str
    tags: List[str]
    
@dataclass
class Association:
    """关联"""
    id: str
    source_event_id: str
    target_id: str
    target_type: DataType
    urgency: UrgencyLevel
    description: str
    value_score: float  # 0.0-1.0
    created_at: datetime
    
@dataclass
class Trip:
    """行程"""
    id: str
    name: str
    start_date: datetime
    end_date: datetime
    location: str
    event_ids: List[str]
    
@dataclass
class DailyEventEntry:
    """每日事件条目"""
    id: str
    original_event_id: str
    date: datetime  # 日期（本地时区）
    label: str
    start_time: datetime
    end_time: datetime
    day_index: int  # 第几天（1-based）
    total_days: int
    
@dataclass
class Conflict:
    """冲突"""
    id: str
    event_ids: List[str]
    severity: ConflictSeverity
    overlap_duration: int  # 分钟
    resolution_suggestions: List[str]
    status: str  # pending, acknowledged, resolved, dismissed
    acknowledged_at: Optional[datetime]  # 用户确认时间
    resolved_at: Optional[datetime]  # 解决时间
    last_notified_at: Optional[datetime]  # 最后通知时间
    
@dataclass
class Alert:
    """预警"""
    id: str
    type: str  # weather, traffic, document, travel_change
    severity: str  # critical, high, medium, low
    title: str
    description: str
    affected_event_ids: List[str]
    actions: List['Action']
    
@dataclass
class Action:
    """行动"""
    id: str
    type: ActionType
    label: str
    is_primary: bool
    context: Dict  # 执行所需的上下文数据
    
@dataclass
class BriefingItem:
    """简报项"""
    id: str
    category: str  # alert, must_do, preparation, suggestion
    priority: int
    title: str
    description: str
    related_event_ids: List[str]
    actions: List[Action]
```

### Value Score Components

```python
@dataclass
class ValueScoreComponents:
    """价值评分组成部分"""
    relevance: float      # 相关性 (0.0-1.0)
    actionability: float  # 可行动性 (0.0-1.0)
    specificity: float    # 具体性 (0.0-1.0)
    composite: float      # 综合评分 (0.0-1.0)
    
    def __post_init__(self):
        """计算综合评分"""
        self.composite = (
            self.relevance * 0.4 +
            self.actionability * 0.4 +
            self.specificity * 0.2
        )
```

## Correctness Properties


*属性（Property）是系统在所有有效执行中都应该保持为真的特征或行为——本质上是关于系统应该做什么的形式化陈述。属性是人类可读规范和机器可验证正确性保证之间的桥梁。*

### Property 1: 关联分类完整性
*对于任何*生成的关联，它必须被分配一个紧急度级别（blocking、recommended或reference）和一个数据类型（person、task、memory、reminder、location），且主分组必须基于紧急度而非数据类型。
**Validates: Requirements 1.1, 1.2, 1.3, 1.4**

### Property 2: 关联价值过滤
*对于任何*关联列表和价值阈值，过滤后的结果中所有关联的value_score都应该大于或等于该阈值，且通用关联应该被排除。
**Validates: Requirements 2.2, 2.3**

### Property 3: 关联价值评分组成
*对于任何*关联，其value_score应该由relevance（相关性）、actionability（可行动性）和specificity（具体性）三个维度计算得出，权重分别为0.4、0.4、0.2，且具有具体行动项或外部引用的关联应该获得更高分数。
**Validates: Requirements 13.1, 13.2, 13.3, 13.4**

### Property 4: 关联优先级排序
*对于任何*关联列表，排序后actionability分数更高的关联应该排在前面。
**Validates: Requirements 2.4**

### Property 5: 关联去重保留最高价值
*对于任何*包含相似关联的列表，去重后应该只保留每组相似关联中value_score最高的那个。
**Validates: Requirements 2.5**

### Property 6: 行程日期连续性
*对于任何*生成的行程，其内部事件之间的日期间隔不应超过2天，且整个行程的日期范围应该是逻辑连续的。
**Validates: Requirements 3.1, 3.2**

### Property 7: 行程地理位置考虑
*对于任何*地理位置相近的事件集合，它们被分配到同一行程的概率应该高于地理位置分散的事件。
**Validates: Requirements 3.3**

### Property 8: 行程时间顺序
*对于任何*行程列表，它们应该按照开始时间的时间顺序排列。
**Validates: Requirements 3.5**

### Property 9: 默认展示blocking级别
*对于任何*事件图谱的初始加载状态，只有urgency为blocking的关联应该被标记为可见。
**Validates: Requirements 4.1**

### Property 10: 展开状态持久化
*对于任何*展开操作，该操作的状态应该在会话期间被正确保存，并在后续访问时恢复。
**Validates: Requirements 4.4**

### Property 11: 隐藏项计数准确性
*对于任何*紧急度级别和关联列表，该级别的隐藏项计数应该等于该级别中未展开的关联的实际数量。
**Validates: Requirements 4.5**

### Property 12: 多天事件拆解完整性
*对于任何*跨越N天的事件，拆解后应该生成恰好N个每日条目，每个条目都保留original_event_id引用原事件。
**Validates: Requirements 5.1, 5.3**

### Property 13: 时区转换正确性
*对于任何*事件，存储时应该使用UTC时间戳，显示时应该转换为用户本地时区，且拆解多天事件时应该保留时区信息。
**Validates: Requirements 14.1, 14.2, 14.5**

### Property 14: 跨时区事件显示
*对于任何*发生在不同时区的事件，显示时应该同时包含用户本地时区和事件所在时区的时间信息。
**Validates: Requirements 14.4**

### Property 15: 跨午夜事件拆解
*对于任何*跨越午夜的事件，应该在用户本地时区的日期边界处被拆分为两个独立的每日条目。
**Validates: Requirements 5.5**

### Property 16: 智能标签生成
*对于任何*多天事件的每日条目，生成的标签应该包含行程名称（如果属于行程）、日期序号和关键活动描述，而不是仅仅使用"Day N"这样的通用标签，且标签长度应该在合理范围内（不超过100字符）。
**Validates: Requirements 6.1, 6.2, 6.3, 6.4, 6.5**

### Property 17: 冲突检测完整性
*对于任何*事件列表，检测到的冲突应该包含所有时间上实际重叠的事件对，且每个冲突都应该根据事件优先级和重叠时长计算出严重程度。
**Validates: Requirements 7.1, 7.4**

### Property 18: 冲突可视化标记
*对于任何*存在时间冲突的事件，在渲染结果中应该包含冲突标记。
**Validates: Requirements 7.2**

### Property 38: 冲突状态持久化
*对于任何*被用户确认（acknowledged）、忽略（dismissed）或解决（resolved）的冲突，系统应该记录其状态，且在后续检测中不应该再次通知用户。
**Validates: Requirements 7.6, 7.7, 16.2, 16.3, 16.4, 16.9**

### Property 39: 冲突ID唯一性和变化检测
*对于任何*冲突，其ID应该基于涉及的事件ID和重叠时间范围计算，当事件被修改导致重叠范围改变时，冲突ID应该改变，系统应该将其视为新冲突。
**Validates: Requirements 7.10, 16.5, 16.6, 16.7**

### Property 40: 冲突通知冷却期
*对于任何*在冷却期（默认24小时）内已经通知过的冲突，系统不应该再次发送通知，除非冲突ID发生变化。
**Validates: Requirements 7.9, 16.8, 16.10**

### Property 41: 冲突通知过滤
*对于任何*冲突检测结果，只有状态为pending且未在冷却期内通知过的冲突才应该被发送给用户。
**Validates: Requirements 7.8, 16.9**

### Property 19: 行程视图分组正确性
*对于任何*在trip-based视图模式下的时光轴，属于同一行程的所有事件应该被分到同一个组，且组头部应该包含行程的名称、日期范围和位置信息。
**Validates: Requirements 8.2, 8.3**

### Property 20: 行程过滤准确性
*对于任何*指定的行程过滤条件，过滤后显示的事件应该只包含属于该行程的事件。
**Validates: Requirements 8.5**

### Property 21: 简报section排序
*对于任何*生成的每日简报，sections应该按照以下顺序排列：alerts（预警）、must-do items（必做事项）、preparation reminders（准备提醒）、suggestions（建议）。
**Validates: Requirements 9.1**

### Property 22: 简报section数量限制
*对于任何*简报section，其包含的items数量不应超过预定义的阈值（例如每个section最多10项）。
**Validates: Requirements 9.2**

### Property 23: 空section隐藏
*对于任何*生成的简报，不包含任何items的section不应该出现在最终输出中。
**Validates: Requirements 9.3**

### Property 24: 简报摘要计数准确性
*对于任何*简报，顶部显示的摘要计数应该等于各优先级items的实际数量总和。
**Validates: Requirements 9.4**

### Property 25: 天气预警生成
*对于任何*包含户外活动标签的事件，如果当天天气条件恶劣，应该生成相应的天气预警。
**Validates: Requirements 10.1**

### Property 26: 交通预警生成
*对于任何*需要出行且发生在高峰时段的事件，应该生成交通预警。
**Validates: Requirements 10.2**

### Property 27: 证件提醒生成
*对于任何*需要身份证明文件的事件（如机场、酒店、政府机构），应该生成证件提醒。
**Validates: Requirements 10.3**

### Property 28: 行程变更预警
*对于任何*航班或火车事件，应该检查时刻表变更并在发现变更时生成预警。
**Validates: Requirements 10.4**

### Property 29: 预警优先级排序
*对于任何*预警列表，应该按照对用户日程的潜在影响程度排序，影响更大的预警排在前面。
**Validates: Requirements 10.5**

### Property 30: 行动按钮存在性
*对于任何*简报中的item，应该至少包含一个可执行的行动按钮。
**Validates: Requirements 11.1**

### Property 31: 行动类型上下文匹配
*对于任何*简报item，生成的行动类型应该与事件类型相关（例如，会议事件应该有"导航"或"拨打电话"行动，待办事项应该有"标记完成"行动）。
**Validates: Requirements 11.2**

### Property 32: 主行动按钮优先级
*对于任何*简报item的行动列表，标记为is_primary=true的行动应该是最相关和最常用的行动。
**Validates: Requirements 11.4**

### Property 33: 外部数据同步
*对于任何*可用的外部日历数据，在处理前应该被同步到curated_events中。
**Validates: Requirements 12.2**

### Property 34: 外部源不可用时的容错
*对于任何*外部数据源不可用的情况，系统应该能够仅使用curated_events继续正常运行。
**Validates: Requirements 12.4**

### Property 35: 同步失败错误信息
*对于任何*数据同步失败的情况，系统应该返回清晰的错误信息，说明失败原因。
**Validates: Requirements 12.5**

### Property 36: 缓存失效正确性
*对于任何*计算出的关联，应该被缓存，且只有当源数据（curated_events）发生变化时才失效重新计算。
**Validates: Requirements 15.4**

### Property 37: LLM请求超时fallback
*对于任何*LLM处理请求，应该实现超时机制，超时时应该有fallback逻辑确保系统继续运行。
**Validates: Requirements 15.5**

## Error Handling

### Error Categories

1. **Data Validation Errors**
   - 无效的事件数据（缺少必需字段）
   - 无效的时间范围（结束时间早于开始时间）
   - 无效的时区信息

2. **External Service Errors**
   - LLM API调用失败或超时
   - 外部日历同步失败
   - 天气/交通API不可用

3. **Business Logic Errors**
   - 无法生成有效的行程分组
   - 关联价值评分计算失败
   - 冲突检测异常

4. **Performance Errors**
   - 响应时间超过阈值
   - 内存使用超限
   - 缓存失效过于频繁

### Error Handling Strategies

**Graceful Degradation**:
```python
def generate_associations_with_fallback(event_id: str) -> List[Association]:
    """
    生成关联，带fallback机制
    """
    try:
        # 尝试使用LLM生成
        associations = llm_generate_associations(event_id, timeout=5.0)
        return associations
    except TimeoutError:
        # Fallback: 使用基于规则的简单关联
        logger.warning(f"LLM timeout for event {event_id}, using rule-based fallback")
        return rule_based_associations(event_id)
    except Exception as e:
        # 最终fallback: 返回空列表
        logger.error(f"Failed to generate associations: {e}")
        return []
```

**Validation and Sanitization**:
```python
def validate_event(event: Event) -> ValidationResult:
    """
    验证事件数据
    """
    errors = []
    
    if not event.id:
        errors.append("Event ID is required")
    
    if not event.title:
        errors.append("Event title is required")
    
    if event.end_time <= event.start_time:
        errors.append("End time must be after start time")
    
    try:
        pytz.timezone(event.timezone)
    except pytz.exceptions.UnknownTimeZoneError:
        errors.append(f"Invalid timezone: {event.timezone}")
    
    return ValidationResult(is_valid=len(errors) == 0, errors=errors)
```

**Circuit Breaker for External Services**:
```python
class CircuitBreaker:
    """
    熔断器模式，防止外部服务故障影响系统
    """
    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
    
    def call(self, func, *args, **kwargs):
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.timeout:
                self.state = "HALF_OPEN"
            else:
                raise CircuitBreakerOpenError("Circuit breaker is open")
        
        try:
            result = func(*args, **kwargs)
            if self.state == "HALF_OPEN":
                self.state = "CLOSED"
                self.failure_count = 0
            return result
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()
            if self.failure_count >= self.failure_threshold:
                self.state = "OPEN"
            raise e
```

**Retry with Exponential Backoff**:
```python
def sync_external_calendar_with_retry(calendar_id: str, max_retries: int = 3):
    """
    同步外部日历，带重试机制
    """
    for attempt in range(max_retries):
        try:
            return sync_external_calendar(calendar_id)
        except TransientError as e:
            if attempt == max_retries - 1:
                raise
            wait_time = 2 ** attempt  # 指数退避
            logger.warning(f"Sync failed, retrying in {wait_time}s: {e}")
            time.sleep(wait_time)
```

## Testing Strategy

### Dual Testing Approach

本系统采用单元测试和基于属性的测试（Property-Based Testing）相结合的策略：

**单元测试（Unit Tests）**:
- 验证特定示例和边界情况
- 测试错误条件和异常处理
- 测试组件之间的集成点
- 使用pytest框架

**基于属性的测试（Property-Based Tests）**:
- 验证跨所有输入的通用属性
- 通过随机化实现全面的输入覆盖
- 使用Hypothesis库（Python）
- 每个属性测试至少运行100次迭代

### Property-Based Testing Configuration

**选择的PBT库**: Hypothesis (Python)

**配置要求**:
```python
from hypothesis import given, settings
import hypothesis.strategies as st

@settings(max_examples=100)  # 最少100次迭代
@given(
    event=st.builds(Event, ...),
    user_timezone=st.sampled_from(pytz.all_timezones)
)
def test_property_12_multi_day_decomposition(event, user_timezone):
    """
    Feature: schedule-organization-optimization
    Property 12: 多天事件拆解完整性
    
    对于任何跨越N天的事件，拆解后应该生成恰好N个每日条目，
    每个条目都保留original_event_id引用原事件。
    """
    # 确保事件跨越多天
    assume(event.is_multi_day())
    
    decomposer = MultiDayEventDecomposer()
    daily_entries = decomposer.decompose_event(event, user_timezone)
    
    expected_days = event.get_day_count(user_timezone)
    
    # 验证条目数量
    assert len(daily_entries) == expected_days
    
    # 验证每个条目都引用原事件
    for entry in daily_entries:
        assert entry.original_event_id == event.id
```

### Test Coverage by Requirement

**事件图谱模块**:
- Property 1-11: 分类、价值评分、行程分组、分层展示
- Unit tests: 边界情况（空关联列表、单个事件、极端价值分数）

**时光轴模块**:
- Property 12-20: 多天事件拆解、时区处理、冲突检测、视图切换
- Unit tests: DST转换、跨年事件、单日事件

**简报模块**:
- Property 21-32: 排序、预警生成、行动按钮
- Unit tests: 空简报、单项简报、外部API失败

**系统级**:
- Property 33-37: 数据同步、缓存、容错
- Unit tests: 网络故障、超时、数据损坏

### Integration Testing

除了单元测试和属性测试，还需要集成测试验证：

1. **端到端流程**: 从curated_events读取 → 生成关联 → 展示图谱/时光轴/简报
2. **外部服务集成**: Google Calendar同步、天气API、交通API
3. **性能测试**: 响应时间、内存使用、并发处理

### Test Data Generation

使用Hypothesis的strategies生成测试数据：

```python
import hypothesis.strategies as st
from datetime import datetime, timedelta

# 事件策略
event_strategy = st.builds(
    Event,
    id=st.uuids().map(str),
    title=st.text(min_size=1, max_size=100),
    start_time=st.datetimes(
        min_value=datetime(2024, 1, 1),
        max_value=datetime(2025, 12, 31)
    ),
    end_time=st.datetimes(
        min_value=datetime(2024, 1, 1),
        max_value=datetime(2025, 12, 31)
    ),
    location=st.one_of(st.none(), st.text(max_size=200)),
    priority=st.integers(min_value=1, max_value=5),
    timezone=st.sampled_from(pytz.all_timezones)
).filter(lambda e: e.end_time > e.start_time)

# 关联策略
association_strategy = st.builds(
    Association,
    urgency=st.sampled_from(list(UrgencyLevel)),
    target_type=st.sampled_from(list(DataType)),
    value_score=st.floats(min_value=0.0, max_value=1.0)
)
```

### Mocking External Dependencies

对于外部依赖（LLM、天气API等），使用mock进行测试：

```python
from unittest.mock import Mock, patch

def test_weather_alert_generation_with_mock():
    """测试天气预警生成（使用mock）"""
    mock_weather_api = Mock()
    mock_weather_api.get_forecast.return_value = {
        "condition": "heavy_rain",
        "temperature": 15
    }
    
    engine = AlertGenerationEngine(weather_api=mock_weather_api)
    
    outdoor_event = Event(
        id="event1",
        title="户外团建",
        tags=["outdoor"],
        start_time=datetime(2024, 6, 1, 10, 0),
        end_time=datetime(2024, 6, 1, 16, 0)
    )
    
    alerts = engine.generate_weather_alerts([outdoor_event], datetime(2024, 6, 1))
    
    assert len(alerts) > 0
    assert alerts[0].type == "weather"
    assert "heavy_rain" in alerts[0].description.lower()
```

## Implementation Notes

### Technology Stack

- **Backend**: Python 3.11+
- **Testing**: pytest, Hypothesis
- **Time Handling**: pytz, python-dateutil
- **Caching**: Redis (for distributed caching)
- **Database**: PostgreSQL (for conflict status persistence)
- **LLM Integration**: OpenAI API / Anthropic API
- **External APIs**: Google Calendar API, Weather API, Traffic API

### Performance Considerations

1. **Lazy Loading**: 时光轴使用虚拟滚动，只渲染可见范围的事件
2. **Caching Strategy**: 
   - 关联结果缓存24小时
   - 行程分组缓存直到事件变更
   - 简报缓存到当天结束
   - 冲突状态持久化到数据库，避免重复计算
3. **Batch Processing**: 批量处理多个事件的关联生成，减少LLM API调用
4. **Database Indexing**: 
   - 在curated_events表上为start_time、end_time、tags建立索引
   - 在conflicts表上为conflict_id、status、last_notified_at建立索引
5. **Conflict Notification Optimization**:
   - 使用conflict_id作为去重键
   - 在内存中维护最近24小时的通知记录，避免数据库查询
   - 定期清理已解决或过期的冲突记录

### Security Considerations

1. **API Key Management**: 使用环境变量或密钥管理服务存储API密钥
2. **Input Validation**: 所有用户输入都需要验证和清理
3. **Rate Limiting**: 对LLM和外部API调用实施速率限制
4. **Data Privacy**: 用户日程数据加密存储，传输使用HTTPS

### Deployment Strategy

1. **Staged Rollout**: 
   - Phase 1: 事件图谱优化
   - Phase 2: 时光轴优化 + 冲突状态管理
   - Phase 3: 简报优化
2. **Feature Flags**: 使用feature flags控制新功能的启用
3. **Monitoring**: 监控响应时间、错误率、LLM调用成功率、冲突通知频率
4. **Rollback Plan**: 保留旧版本代码，支持快速回滚

### Database Schema for Conflict Management

```sql
-- 冲突状态表
CREATE TABLE conflict_status (
    conflict_id VARCHAR(64) PRIMARY KEY,
    event_ids TEXT[] NOT NULL,  -- 涉及的事件ID数组
    status VARCHAR(20) NOT NULL CHECK (status IN ('pending', 'acknowledged', 'resolved', 'dismissed')),
    severity VARCHAR(20) NOT NULL,
    overlap_start TIMESTAMP WITH TIME ZONE NOT NULL,
    overlap_end TIMESTAMP WITH TIME ZONE NOT NULL,
    overlap_duration_minutes INTEGER NOT NULL,
    user_id VARCHAR(64) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    acknowledged_at TIMESTAMP WITH TIME ZONE,
    resolved_at TIMESTAMP WITH TIME ZONE,
    last_notified_at TIMESTAMP WITH TIME ZONE,
    notification_count INTEGER DEFAULT 0
);

-- 索引
CREATE INDEX idx_conflict_status_user_status ON conflict_status(user_id, status);
CREATE INDEX idx_conflict_status_last_notified ON conflict_status(last_notified_at);
CREATE INDEX idx_conflict_event_ids ON conflict_status USING GIN(event_ids);

-- 定期清理已解决或过期的冲突（保留30天）
CREATE INDEX idx_conflict_cleanup ON conflict_status(status, resolved_at) 
WHERE status IN ('resolved', 'dismissed');
```

### Conflict Notification Logic

```python
def get_conflicts_to_notify(
    user_id: str,
    detected_conflicts: List[Conflict],
    cooldown_hours: int = 24
) -> List[Conflict]:
    """
    获取需要通知用户的冲突列表
    
    过滤规则：
    1. 排除已确认、已解决、已忽略的冲突
    2. 排除在冷却期内已通知过的冲突
    3. 只包含新检测到的冲突（数据库中不存在）
    """
    conflicts_to_notify = []
    cooldown_threshold = datetime.now() - timedelta(hours=cooldown_hours)
    
    # 从数据库获取现有冲突状态
    existing_conflicts = db.query(ConflictStatus).filter(
        ConflictStatus.user_id == user_id,
        ConflictStatus.status.in_(['pending', 'acknowledged', 'resolved', 'dismissed'])
    ).all()
    
    existing_conflict_map = {c.conflict_id: c for c in existing_conflicts}
    
    for conflict in detected_conflicts:
        conflict_id = conflict.id
        
        # 检查是否是新冲突
        if conflict_id not in existing_conflict_map:
            # 新冲突，需要通知
            conflicts_to_notify.append(conflict)
            # 创建数据库记录
            db.add(ConflictStatus(
                conflict_id=conflict_id,
                event_ids=conflict.event_ids,
                status='pending',
                severity=conflict.severity,
                user_id=user_id,
                last_notified_at=datetime.now(),
                notification_count=1
            ))
        else:
            existing = existing_conflict_map[conflict_id]
            
            # 检查状态
            if existing.status in ['acknowledged', 'resolved', 'dismissed']:
                # 已处理，不通知
                continue
            
            # 检查冷却期
            if existing.last_notified_at and existing.last_notified_at > cooldown_threshold:
                # 在冷却期内，不通知
                continue
            
            # 超过冷却期的pending冲突，再次通知
            conflicts_to_notify.append(conflict)
            existing.last_notified_at = datetime.now()
            existing.notification_count += 1
    
    db.commit()
    return conflicts_to_notify
```
