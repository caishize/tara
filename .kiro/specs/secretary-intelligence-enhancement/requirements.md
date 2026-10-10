# Requirements Document

## Introduction

本文档定义了日程整理系统的秘书智能增强功能需求。系统应该像一个真实的秘书一样，不仅管理日程，还能主动发现机会、提供洞察、记住老板说过的话，并在合适的时机给出智能建议。

当前系统虽然具备基本的日程管理和关联发现功能，但在记忆关联、上下文理解、智能推荐等方面还不够"秘书化"。本需求旨在增强系统的智能性，使其能够：
- 记住用户的社交意图和偏好
- 发现隐藏的机会（顺便可做的事情）
- 提供基于历史记忆的个性化建议
- 智能处理日程冲突

## Glossary

- **System**: 日程整理系统（Schedule Organization System）
- **Secretary_Intelligence**: 秘书智能模块，负责记忆关联、机会发现、洞察生成
- **Memory_Engine**: 记忆引擎，负责查询和关联各类记忆（对话、事件、社交意图）
- **Association_Discoverer**: 关联发现器，负责发现事件之间的关联和"顺便可做"的机会
- **Context_Enricher**: 上下文增强器，为事件添加背景信息和相关记忆
- **Conflict_Resolver**: 冲突解决器，不仅检测冲突，还提供解决方案
- **Briefing_Generator**: 简报生成器，生成秘书式的每日汇报
- **Social_Intent**: 社交意图，用户表达的社交愿望（如"想见某人"、"要送礼物"）
- **Opportunity**: 机会，系统发现的"顺便可做"的事情
- **Insight**: 洞察，基于历史记忆和当前情况的智能建议
- **ConversationMemory**: 对话记忆，存储用户对话中的信息
- **EventAssociation**: 事件关联，存储事件之间的关联关系
- **CuratedEvent**: 策展事件，经过整理和增强的事件

## Requirements

### Requirement 1: 增强记忆查询能力

**User Story:** 作为用户，我希望系统能够记住我说过的话和表达的意图，以便在合适的时机主动提醒我。

#### Acceptance Criteria

1. WHEN 用户表达社交意图（如"下次去北京要约张三吃饭"）THEN THE Memory_Engine SHALL 识别并存储该意图，包括触发条件（地点）、目标人物、行动类型
2. WHEN 系统查询相关记忆时 THEN THE Memory_Engine SHALL 查询多种记忆源（ConversationMemory、Social_Intent、历史事件），而不仅限于对话记忆
3. WHEN 查询记忆时 THEN THE Memory_Engine SHALL 按相关性排序结果，考虑地点匹配、人物匹配、时间接近度、语义相似度
4. WHEN 记忆数量超过查询限制时 THEN THE Memory_Engine SHALL 优先返回最相关的记忆，而不是最新的记忆
5. WHEN 用户创建新事件时 THEN THE Memory_Engine SHALL 自动检查是否有相关的社交意图需要提醒

### Requirement 2: 智能关联发现

**User Story:** 作为用户，我希望系统能够发现"顺便可做"的事情，让我的行程更高效。

#### Acceptance Criteria

1. WHEN 用户有出差或旅行计划时 THEN THE Association_Discoverer SHALL 查找该地点的联系人、待办事项、历史记忆
2. WHEN 发现潜在关联时 THEN THE Association_Discoverer SHALL 计算关联置信度，考虑地理距离、时间可行性、重要性
3. WHEN 生成关联建议时 THEN THE Association_Discoverer SHALL 分类为"必须做"、"顺便做"、"可以做"三个层级
4. WHEN 用户行程路线经过某地时 THEN THE Association_Discoverer SHALL 建议顺路可办理的事项
5. WHEN 发现重要日期临近时 THEN THE Association_Discoverer SHALL 结合出行计划建议准备礼物或祝福
6. WHEN 用户长时间未联系某人时 THEN THE Association_Discoverer SHALL 在合适的行程中建议见面

### Requirement 3: 上下文增强

**User Story:** 作为用户，我希望每个事件都能显示背景信息，让我知道"为什么"要做这件事。

#### Acceptance Criteria

1. WHEN 系统展示事件时 THEN THE Context_Enricher SHALL 附加事件来源信息（从哪个对话或记忆中提取）
2. WHEN 事件有相关历史时 THEN THE Context_Enricher SHALL 显示相关的历史事件和记忆（如"上次去北京时见了谁"）
3. WHEN 事件涉及人物时 THEN THE Context_Enricher SHALL 显示与该人物的最近互动和人情往来记录
4. WHEN 事件之间有关联时 THEN THE Context_Enricher SHALL 显示跨事件的关联提示（如"这个会议是为了上次提到的项目"）
5. WHEN 用户查看事件详情时 THEN THE Context_Enricher SHALL 提供决策支持信息（如优先级理由、可调整性分析）

### Requirement 4: 智能冲突解决

**User Story:** 作为用户，我希望系统不仅能检测日程冲突，还能给出调整建议。

#### Acceptance Criteria

1. WHEN 检测到日程冲突时 THEN THE Conflict_Resolver SHALL 分析每个事件的可调整性（硬约束 vs 软约束）
2. WHEN 生成解决方案时 THEN THE Conflict_Resolver SHALL 提供多个调整方案，每个方案包含调整理由和影响分析
3. WHEN 评估调整方案时 THEN THE Conflict_Resolver SHALL 考虑事件的重要性、紧急性、机会成本
4. WHEN 建议调整时间时 THEN THE Conflict_Resolver SHALL 检查调整后是否会产生新的冲突
5. WHEN 无法自动解决冲突时 THEN THE Conflict_Resolver SHALL 明确说明冲突原因和需要用户决策的点

### Requirement 5: 秘书式简报生成

**User Story:** 作为用户，我希望每天收到像真实秘书一样的汇报，包含洞察和建议，而不只是事件列表。

#### Acceptance Criteria

1. WHEN 生成每日简报时 THEN THE Briefing_Generator SHALL 按重要性和紧急性排序事件，而不是按时间顺序
2. WHEN 简报包含出行计划时 THEN THE Briefing_Generator SHALL 主动提醒相关的社交意图和顺便可做的事情
3. WHEN 发现机会时 THEN THE Briefing_Generator SHALL 以洞察的形式呈现（如"今天去上海，上次您见了A、B、C，这次可能需要跟进"）
4. WHEN 有重要日期临近时 THEN THE Briefing_Generator SHALL 结合行程给出准备建议
5. WHEN 用户长时间未联系重要人物时 THEN THE Briefing_Generator SHALL 在简报中提醒并建议合适的联系时机
6. WHEN 简报包含冲突时 THEN THE Briefing_Generator SHALL 直接给出解决建议，而不只是列出冲突

### Requirement 6: 图谱分层展示

**User Story:** 作为用户，我希望事件图谱能够清晰地展示"必须做"、"顺便做"、"可以做"的事情。

#### Acceptance Criteria

1. WHEN 生成事件图谱时 THEN THE System SHALL 将事件分为四层：核心行程、必须处理、顺便可做、背景信息
2. WHEN 展示核心行程时 THEN THE System SHALL 突出显示出差、旅行等主要行程
3. WHEN 展示必须处理事项时 THEN THE System SHALL 包含会议、预约、deadline 等硬约束事件
4. WHEN 展示顺便可做事项时 THEN THE System SHALL 显示基于地理位置和时间的机会
5. WHEN 展示背景信息时 THEN THE System SHALL 显示相关的历史记忆和人情往来
6. WHEN 用户点击事件时 THEN THE System SHALL 展示该事件的所有关联和上下文

### Requirement 7: 时光轴关联展示

**User Story:** 作为用户，我希望时光轴不仅显示事件列表，还能展示事件之间的关联和背景。

#### Acceptance Criteria

1. WHEN 展示时光轴时 THEN THE System SHALL 为每个事件显示简短的背景说明（为什么要做这件事）
2. WHEN 多个事件属于同一行程时 THEN THE System SHALL 将它们聚合显示，并标注行程主题
3. WHEN 事件之间有依赖关系时 THEN THE System SHALL 用视觉方式展示关联（如连线、缩进）
4. WHEN 用户悬停或点击事件时 THEN THE System SHALL 显示详细的上下文和相关记忆
5. WHEN 时光轴包含冲突时 THEN THE System SHALL 高亮显示冲突并附带解决建议

### Requirement 8: 性能优化

**User Story:** 作为系统管理员，我希望增强的智能功能不会显著影响系统性能。

#### Acceptance Criteria

1. WHEN 查询记忆时 THEN THE Memory_Engine SHALL 使用索引和缓存机制，确保查询时间在 500ms 以内
2. WHEN 发现关联时 THEN THE Association_Discoverer SHALL 采用增量计算，只处理新增或变更的事件
3. WHEN 生成简报时 THEN THE Briefing_Generator SHALL 使用异步处理，不阻塞用户操作
4. WHEN 系统负载较高时 THEN THE System SHALL 降级处理，优先保证核心功能（事件展示）的响应速度
5. WHEN LLM 调用失败或超时时 THEN THE System SHALL 回退到基于规则的关联发现，确保功能可用性

### Requirement 9: 向后兼容性

**User Story:** 作为开发者，我希望新功能不会破坏现有的系统功能和数据结构。

#### Acceptance Criteria

1. WHEN 增强记忆查询时 THEN THE System SHALL 保持现有的 ConversationMemory、EventAssociation 模型不变
2. WHEN 添加新功能时 THEN THE System SHALL 通过扩展而非修改现有接口来实现
3. WHEN 现有功能调用旧接口时 THEN THE System SHALL 保持原有行为不变
4. WHEN 数据库 schema 需要变更时 THEN THE System SHALL 提供迁移脚本，确保现有数据不丢失
5. WHEN 新功能失败时 THEN THE System SHALL 不影响现有功能的正常运行

### Requirement 10: LLM Prompt 优化

**User Story:** 作为系统设计者，我希望 LLM 能够像真实秘书一样思考和表达。

#### Acceptance Criteria

1. WHEN 调用 LLM 发现关联时 THEN THE System SHALL 使用明确的秘书角色 prompt，强调"顺便可做"的场景
2. WHEN LLM 生成建议时 THEN THE System SHALL 要求 LLM 提供理由和置信度，而不只是结果
3. WHEN LLM 处理社交意图时 THEN THE System SHALL 引导 LLM 识别触发条件、目标人物、行动类型
4. WHEN LLM 生成简报时 THEN THE System SHALL 要求 LLM 以洞察而非列表的形式呈现
5. WHEN LLM 输出结构化数据时 THEN THE System SHALL 使用 JSON schema 约束，确保输出格式正确
