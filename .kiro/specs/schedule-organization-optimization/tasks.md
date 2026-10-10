# Implementation Plan: Schedule Organization Optimization

## Overview

本实施计划将日程整理系统的优化分为三个主要阶段：事件图谱优化、时光轴优化（含冲突状态管理）、简报优化。每个阶段都包含核心实现和对应的测试任务。实现语言为Python 3.11+。

## Tasks

### Phase 1: 事件图谱优化

- [ ] 1. 实现关联价值评分引擎
  - [ ] 1.1 创建ValueScoringEngine类和评分组件数据模型
    - 实现relevance、actionability、specificity三个维度的评分函数
    - 实现综合评分计算（权重：0.4, 0.4, 0.2）
    - _Requirements: 13.1, 13.2, 13.3, 13.4_
  
  - [ ] 1.2 编写价值评分的属性测试
    - **Property 3: 关联价值评分组成**
    - **Validates: Requirements 13.1, 13.2, 13.3, 13.4**
  
  - [ ] 1.3 编写价值评分的单元测试
    - 测试边界情况（0分、满分）
    - 测试权重计算正确性
    - _Requirements: 13.1_

- [ ] 2. 实现关联引擎核心功能
  - [ ] 2.1 创建AssociationEngine类
    - 实现generate_associations方法（集成LLM）
    - 实现calculate_value_score方法
    - 实现filter_low_value_associations方法
    - 实现deduplicate_associations方法
    - _Requirements: 2.1, 2.2, 2.3, 2.5_
  
  - [ ] 2.2 编写关联过滤的属性测试
    - **Property 2: 关联价值过滤**
    - **Validates: Requirements 2.2, 2.3**
  
  - [ ] 2.3 编写关联去重的属性测试
    - **Property 5: 关联去重保留最高价值**
    - **Validates: Requirements 2.5**
  
  - [ ] 2.4 编写关联排序的属性测试
    - **Property 4: 关联优先级排序**
    - **Validates: Requirements 2.4**

- [ ] 3. 实现关联分类和展示逻辑
  - [ ] 3.1 更新Association数据模型
    - 添加urgency字段（UrgencyLevel枚举）
    - 添加target_type字段（DataType枚举）
    - 确保所有关联都有这两个字段
    - _Requirements: 1.1, 1.2, 1.4_
  
  - [ ] 3.2 编写关联分类的属性测试
    - **Property 1: 关联分类完整性**
    - **Validates: Requirements 1.1, 1.2, 1.3, 1.4**
  
  - [ ] 3.3 实现事件图谱分层展示逻辑
    - 实现默认只显示blocking级别的逻辑
    - 实现展开/折叠状态管理
    - 实现隐藏项计数功能
    - _Requirements: 4.1, 4.4, 4.5_
  
  - [ ] 3.4 编写分层展示的属性测试
    - **Property 9: 默认展示blocking级别**
    - **Property 10: 展开状态持久化**
    - **Property 11: 隐藏项计数准确性**
    - **Validates: Requirements 4.1, 4.4, 4.5**

- [ ] 4. 实现行程智能分组引擎
  - [ ] 4.1 创建TripGroupingEngine类
    - 实现group_events_into_trips方法
    - 实现check_date_continuity方法（最大间隔2天）
    - 实现check_location_proximity方法
    - 实现validate_trip_range方法
    - _Requirements: 3.1, 3.2, 3.3_
  
  - [ ] 4.2 编写行程分组的属性测试
    - **Property 6: 行程日期连续性**
    - **Property 7: 行程地理位置考虑**
    - **Property 8: 行程时间顺序**
    - **Validates: Requirements 3.1, 3.2, 3.3, 3.5**
  
  - [ ] 4.3 编写行程分组的单元测试
    - 测试单个事件的情况
    - 测试跨度超过30天的情况
    - 测试地理位置缺失的情况
    - _Requirements: 3.1, 3.3_

- [ ] 5. Checkpoint - 事件图谱模块测试
  - 确保所有测试通过，询问用户是否有问题

### Phase 2: 时光轴优化与冲突管理

- [ ] 6. 实现多天事件强制拆解
  - [ ] 6.1 创建MultiDayEventDecomposer类
    - 实现decompose_event方法（不依赖LLM）
    - 实现handle_midnight_crossing方法
    - 确保保留original_event_id引用
    - 正确处理时区转换
    - _Requirements: 5.1, 5.3, 5.4, 5.5_
  
  - [ ]* 6.2 编写多天事件拆解的属性测试
    - **Property 12: 多天事件拆解完整性**
    - **Property 15: 跨午夜事件拆解**
    - **Validates: Requirements 5.1, 5.3, 5.5**
  
  - [ ]* 6.3 编写时区处理的属性测试
    - **Property 13: 时区转换正确性**
    - **Property 14: 跨时区事件显示**
    - **Validates: Requirements 14.1, 14.2, 14.4, 14.5**
  
  - [ ]* 6.4 编写时区边界情况的单元测试
    - 测试DST转换
    - 测试跨年事件
    - 测试单日事件（不应拆解）
    - _Requirements: 5.1, 14.3_

- [ ] 7. 实现智能标签生成
  - [ ] 7.1 在MultiDayEventDecomposer中实现generate_daily_label方法
    - 生成包含行程名称的标签
    - 生成包含日期序号和关键活动的标签
    - 避免使用通用的"Day N"标签
    - 限制标签长度（最多100字符）
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_
  
  - [ ]* 7.2 编写智能标签生成的属性测试
    - **Property 16: 智能标签生成**
    - **Validates: Requirements 6.1, 6.2, 6.3, 6.4, 6.5**
  
  - [ ]* 7.3 编写标签生成的单元测试
    - 测试不同事件类型的标签
    - 测试超长标签的截断
    - 测试无行程关联的事件
    - _Requirements: 6.1, 6.5_

- [ ] 8. 实现冲突检测引擎
  - [ ] 8.1 创建ConflictDetectionEngine类
    - 实现detect_conflicts方法（扫描线算法）
    - 实现calculate_conflict_severity方法
    - 实现generate_resolution_suggestions方法
    - 实现calculate_conflict_id方法（基于事件ID和重叠时间）
    - _Requirements: 7.1, 7.4, 7.10_
  
  - [ ]* 8.2 编写冲突检测的属性测试
    - **Property 17: 冲突检测完整性**
    - **Property 39: 冲突ID唯一性和变化检测**
    - **Validates: Requirements 7.1, 7.4, 7.10**
  
  - [ ]* 8.3 编写冲突检测的单元测试
    - 测试无冲突的情况
    - 测试多个事件同时冲突
    - 测试部分重叠vs完全重叠
    - _Requirements: 7.1_

- [ ] 9. 实现冲突状态管理系统
  - [ ] 9.1 创建数据库schema
    - 创建conflict_status表
    - 创建必要的索引
    - 实现数据库迁移脚本
    - _Requirements: 16.1, 16.5_
  
  - [ ] 9.2 在ConflictDetectionEngine中实现状态管理方法
    - 实现should_notify_conflict方法
    - 实现update_conflict_status方法
    - 实现get_conflicts_to_notify函数
    - _Requirements: 16.2, 16.3, 16.4, 16.6, 16.7, 16.8, 16.9, 16.10_
  
  - [ ]* 9.3 编写冲突状态管理的属性测试
    - **Property 38: 冲突状态持久化**
    - **Property 40: 冲突通知冷却期**
    - **Property 41: 冲突通知过滤**
    - **Validates: Requirements 7.6, 7.7, 7.8, 7.9, 16.2, 16.3, 16.4, 16.9, 16.10**
  
  - [ ]* 9.4 编写冲突状态管理的单元测试
    - 测试状态转换（pending → acknowledged → resolved）
    - 测试冷却期边界情况
    - 测试数据库持久化
    - _Requirements: 16.1, 16.8_

- [ ] 10. 实现时光轴视图功能
  - [ ] 10.1 实现时光轴冲突可视化
    - 在Timeline模块中集成ConflictDetectionEngine
    - 实现冲突标记渲染逻辑
    - _Requirements: 7.2_
  
  - [ ]* 10.2 编写冲突可视化的属性测试
    - **Property 18: 冲突可视化标记**
    - **Validates: Requirements 7.2**
  
  - [ ] 10.3 实现行程视图分组
    - 实现date-based和trip-based视图切换
    - 实现trip-based分组逻辑
    - 实现行程元数据展示
    - 实现行程过滤功能
    - _Requirements: 8.2, 8.3, 8.5_
  
  - [ ]* 10.4 编写行程视图的属性测试
    - **Property 19: 行程视图分组正确性**
    - **Property 20: 行程过滤准确性**
    - **Validates: Requirements 8.2, 8.3, 8.5**

- [ ] 11. Checkpoint - 时光轴模块测试
  - 确保所有测试通过，询问用户是否有问题

### Phase 3: 简报优化

- [ ] 12. 实现预警生成引擎
  - [ ] 12.1 创建AlertGenerationEngine类
    - 实现generate_weather_alerts方法
    - 实现generate_traffic_alerts方法
    - 实现generate_document_reminders方法
    - 实现check_travel_schedule_changes方法
    - 实现prioritize_alerts方法
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_
  
  - [ ]* 12.2 编写预警生成的属性测试
    - **Property 25: 天气预警生成**
    - **Property 26: 交通预警生成**
    - **Property 27: 证件提醒生成**
    - **Property 28: 行程变更预警**
    - **Property 29: 预警优先级排序**
    - **Validates: Requirements 10.1, 10.2, 10.3, 10.4, 10.5**
  
  - [ ]* 12.3 编写预警生成的单元测试（使用mock）
    - Mock天气API
    - Mock交通API
    - Mock航班查询API
    - 测试API失败的fallback
    - _Requirements: 10.1, 10.2, 10.4_

- [ ] 13. 实现行动生成器
  - [ ] 13.1 创建ActionGenerator类
    - 实现generate_actions方法
    - 实现prioritize_actions方法
    - 实现create_quick_action方法
    - 支持多种行动类型（NAVIGATE, CALL, RESCHEDULE等）
    - _Requirements: 11.1, 11.2, 11.4_
  
  - [ ]* 13.2 编写行动生成的属性测试
    - **Property 30: 行动按钮存在性**
    - **Property 31: 行动类型上下文匹配**
    - **Property 32: 主行动按钮优先级**
    - **Validates: Requirements 11.1, 11.2, 11.4**
  
  - [ ]* 13.3 编写行动生成的单元测试
    - 测试不同事件类型的行动生成
    - 测试主按钮选择逻辑
    - _Requirements: 11.1, 11.2_

- [ ] 14. 实现简报生成逻辑
  - [ ] 14.1 创建DailyBriefing模块
    - 实现简报section排序（alerts → must-do → preparation → suggestions）
    - 实现section数量限制
    - 实现空section隐藏
    - 实现摘要计数功能
    - _Requirements: 9.1, 9.2, 9.3, 9.4_
  
  - [ ]* 14.2 编写简报生成的属性测试
    - **Property 21: 简报section排序**
    - **Property 22: 简报section数量限制**
    - **Property 23: 空section隐藏**
    - **Property 24: 简报摘要计数准确性**
    - **Validates: Requirements 9.1, 9.2, 9.3, 9.4**
  
  - [ ]* 14.3 编写简报生成的单元测试
    - 测试空简报
    - 测试单section简报
    - 测试所有section都有内容的情况
    - _Requirements: 9.1, 9.3_

- [ ] 15. Checkpoint - 简报模块测试
  - 确保所有测试通过，询问用户是否有问题

### Phase 4: 系统级优化与集成

- [ ] 16. 实现数据源简化
  - [ ] 16.1 实现外部日历同步逻辑
    - 实现Google Calendar同步
    - 实现Outlook同步
    - 确保同步到curated_events
    - _Requirements: 12.2_
  
  - [ ]* 16.2 编写数据同步的属性测试
    - **Property 33: 外部数据同步**
    - **Validates: Requirements 12.2**
  
  - [ ] 16.3 实现容错和错误处理
    - 实现外部源不可用时的fallback
    - 实现清晰的错误信息
    - 实现熔断器模式
    - _Requirements: 12.4, 12.5_
  
  - [ ]* 16.4 编写容错的属性测试
    - **Property 34: 外部源不可用时的容错**
    - **Property 35: 同步失败错误信息**
    - **Validates: Requirements 12.4, 12.5**

- [ ] 17. 实现缓存和性能优化
  - [ ] 17.1 实现Redis缓存层
    - 实现关联结果缓存（24小时）
    - 实现行程分组缓存
    - 实现简报缓存
    - 实现缓存失效逻辑
    - _Requirements: 15.4_
  
  - [ ]* 17.2 编写缓存的属性测试
    - **Property 36: 缓存失效正确性**
    - **Validates: Requirements 15.4**
  
  - [ ] 17.3 实现LLM请求超时和fallback
    - 实现5秒超时
    - 实现基于规则的fallback
    - 实现重试机制（指数退避）
    - _Requirements: 15.5_
  
  - [ ]* 17.4 编写LLM容错的属性测试
    - **Property 37: LLM请求超时fallback**
    - **Validates: Requirements 15.5**
  
  - [ ]* 17.5 编写性能测试
    - 测试事件图谱加载时间（100个关联 < 500ms）
    - 测试简报生成时间（10-20个事件 < 1s）
    - _Requirements: 15.1, 15.3_

- [ ] 18. 集成测试和端到端测试
  - [ ]* 18.1 编写端到端集成测试
    - 测试完整流程：读取curated_events → 生成关联 → 展示图谱
    - 测试完整流程：拆解多天事件 → 检测冲突 → 展示时光轴
    - 测试完整流程：生成预警 → 生成行动 → 展示简报
  
  - [ ]* 18.2 编写外部服务集成测试
    - 测试Google Calendar集成
    - 测试天气API集成
    - 测试交通API集成

- [ ] 19. 最终Checkpoint
  - 运行所有测试套件
  - 检查代码覆盖率
  - 询问用户是否准备部署

## Notes

- 任务标记为 `*` 的是可选测试任务，可以跳过以加快MVP开发
- 每个任务都引用了具体的需求编号，确保可追溯性
- Checkpoint任务确保增量验证
- 属性测试使用Hypothesis库，每个测试至少运行100次迭代
- 单元测试使用pytest框架
- 所有外部依赖（LLM、天气API等）在测试中使用mock
