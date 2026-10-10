# Implementation Plan: Secretary Intelligence Enhancement

## Overview

本实施计划采用彻底重构策略，重新设计整个秘书智能系统。重构将分4个阶段进行，每个阶段都有明确的里程碑和验收标准。

## Tasks

- [ ] 1. Phase 1: Memory System Refactoring (记忆系统重构)
  - [x] 1.1 Create SocialIntent model and database migration
    - Create `backend/src/modules/secretary/models/social_intent.py`
    - Define SocialIntent model with fields: intent_type, target_person_id, trigger_type, trigger_location, etc.
    - Create Alembic migration script for social_intents table
    - Add indexes on family_id, trigger_location, trigger_date, status
    - _Requirements: 1.1_
  
  - [x] 1.2 Implement social intent extraction from conversation memories
    - Create `backend/src/modules/secretary/services/memory_engine.py`
    - Implement `extract_social_intent()` method using LLM
    - Create LLM prompt for social intent extraction (SOCIAL_INTENT_EXTRACTION_PROMPT)
    - Parse LLM response and create SocialIntent records
    - _Requirements: 1.1_
  
  - [x] 1.3 Write property test for social intent extraction
    - **Property 1: Social Intent Extraction Completeness**
    - **Validates: Requirements 1.1**
  
  - [x] 1.4 Implement multi-source memory query
    - Implement `query_relevant_memories()` in MemoryEngine
    - Query ConversationMemory, SocialIntent, and historical CuratedEvents
    - Merge results from all sources
    - _Requirements: 1.2_
  
  - [x] 1.5 Write property test for multi-source query
    - **Property 2: Multi-Source Memory Query Completeness**
    - **Validates: Requirements 1.2**
  
  - [x] 1.6 Implement relevance scoring algorithm
    - Implement `calculate_relevance_score()` function
    - Score based on location match (40%), person match (30%), time proximity (20%), semantic similarity (10%)
    - Sort memories by relevance score
    - _Requirements: 1.3, 1.4_
  
  - [x] 1.7 Write property test for relevance ordering
    - **Property 3: Memory Relevance Ordering**
    - **Validates: Requirements 1.3, 1.4**
  
  - [x] 1.8 Implement social intent trigger detection
    - Implement `check_triggered_intents()` in MemoryEngine
    - Match event location/date/type against intent triggers
    - Return list of triggered intents
    - _Requirements: 1.5_
  
  - [x] 1.9 Write property test for trigger detection
    - **Property 4: Social Intent Trigger Detection**
    - **Validates: Requirements 1.5**

- [ ] 2. Phase 2: Rule-Based Association Engine (规则引擎)
  - [x] 2.1 Create RuleBasedAssociationEngine class
    - Create `backend/src/modules/secretary/services/rule_engine.py`
    - Define RuleBasedAssociationEngine class structure
    - Implement base `discover_associations()` method
    - _Requirements: 2.1_
  
  - [x] 2.2 Implement location-based person matching rule
    - Find members whose location matches event location
    - Calculate geographic distance
    - Create location-type associations with confidence 0.85
    - _Requirements: 2.1_
  
  - [x] 2.3 Implement date-based important date matching rule
    - Find ImportantDates within 7 days of event date
    - Create temporal-type associations with confidence 0.9
    - _Requirements: 2.5_
  
  - [x] 2.4 Write property test for important date matching
    - **Property 9: Important Date Preparation Reminder**
    - **Validates: Requirements 2.5**
  
  - [x] 2.5 Implement social intent matching rule
    - Check triggered intents from MemoryEngine
    - Create memory-type associations with confidence 0.95
    - _Requirements: 2.1_
  
  - [x] 2.6 Implement stale contact detection rule
    - Find contacts not interacted with for >90 days
    - Filter by event location
    - Create person-type associations with confidence 0.7
    - _Requirements: 2.6_
  
  - [x] 2.7 Write property test for stale contact detection
    - **Property 10: Stale Contact Detection**
    - **Validates: Requirements 2.6**
  
  - [x] 2.8 Implement route-based task matching rule
    - Find tasks along event route (within distance threshold)
    - Create task-type associations
    - _Requirements: 2.4_
  
  - [x] 2.9 Write property test for route-based task discovery
    - **Property 8: Route-Based Task Discovery**
    - **Validates: Requirements 2.4**
  
  - [x] 2.10 Implement association confidence calculation
    - Implement `calculate_association_confidence()` function
    - Consider geographic distance, time feasibility, importance
    - Return confidence score 0.0-1.0
    - _Requirements: 2.2_
  
  - [x] 2.11 Write property test for confidence calculation
    - **Property 6: Association Confidence Calculation**
    - **Validates: Requirements 2.2**

- [x] 3. Checkpoint - Ensure memory system and rule engine tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 4. Phase 3: Enhanced Association Discovery (关联发现增强)
  - [x] 4.1 Refactor `_discover_associations()` method in SecretaryCurationService
    - Rewrite method to use both LLM and rule engine
    - Call rule_engine.discover_associations() first
    - Call LLM discovery second
    - Merge and deduplicate results
    - _Requirements: 2.1_
  
  - [x] 4.2 Write property test for association discovery completeness
    - **Property 5: Association Discovery Completeness**
    - **Validates: Requirements 2.1**
  
  - [x] 4.3 Update ASSOCIATION_SYSTEM_PROMPT to ENHANCED_ASSOCIATION_PROMPT
    - Replace existing prompt with enhanced version from design
    - Emphasize "secretary thinking" and "convenient opportunities"
    - Add quality standards to prevent generic reminders
    - _Requirements: 10.1_
  
  - [x] 4.4 Implement association priority classification
    - Classify associations into strongly_recommend, convenient, optional
    - Based on user intent explicitness, time urgency, opportunity rarity
    - _Requirements: 2.3_
  
  - [x] 4.5 Write property test for priority classification
    - **Property 7: Association Priority Classification**
    - **Validates: Requirements 2.3**
  
  - [x] 4.6 Implement association merging and deduplication
    - Merge rule-based and LLM-based associations
    - Deduplicate by (source_event_id, title)
    - Keep higher confidence when duplicates exist
    - _Requirements: 2.1_
  
  - [x] 4.7 Implement low-quality association filtering
    - Filter out generic reminders (e.g., "check documents")
    - Keep only actionable, specific suggestions
    - Limit to max 8 associations per event
    - _Requirements: 10.1_
  
  - [x] 4.8 Implement LLM fallback mechanism
    - Create LLMErrorHandler class
    - Implement `call_llm_with_fallback()` method
    - Handle timeout, format errors, empty results
    - Fall back to rule engine on LLM failure
    - _Requirements: 8.5_
  
  - [x] 4.9 Write unit test for LLM fallback
    - Test LLM timeout scenario
    - Test LLM format error scenario
    - Verify fallback to rule engine
    - _Requirements: 8.5_

- [ ] 5. Phase 4: Context Enrichment (上下文增强)
  - [x] 5.1 Create ContextEnricher class
    - Create `backend/src/modules/secretary/services/context_enricher.py`
    - Define EventContext data model
    - Implement base `enrich_event()` method
    - _Requirements: 3.1_
  
  - [x] 5.2 Implement source information extraction
    - Extract source_info from event.original_event_ids
    - Generate source_summary (e.g., "来自1月15日与助手的对话")
    - _Requirements: 3.1_
  
  - [x] 5.3 Implement historical event query
    - Query CuratedEvents with same location in past 6 months
    - Generate historical_summary (e.g., "上次去北京见了张三、李四")
    - _Requirements: 3.2_
  
  - [x] 5.4 Implement related people query
    - Find members involved in event or at event location
    - Query recent interactions with these members
    - Generate people_summary
    - _Requirements: 3.3_
  
  - [x] 5.5 Implement event chain discovery
    - Find events with dependencies (e.g., "this meeting is for the project mentioned last time")
    - Generate event_chain_summary
    - _Requirements: 3.4_
  
  - [x] 5.6 Implement decision support information generation
    - Analyze priority_reason based on event type, importance, associations
    - Analyze adjustability (hard_constraint, soft_constraint, flexible)
    - Generate adjustability_reason
    - _Requirements: 3.5_
  
  - [x] 5.7 Write property test for context enrichment
    - **Property 11: Event Context Enrichment**
    - **Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5**
  
  - [x] 5.8 Integrate ContextEnricher into timeline and graph APIs
    - Update `get_curated_timeline()` to enrich events
    - Update `get_curated_graph()` to enrich core event
    - Store enriched context in event.enrichments JSON field
    - _Requirements: 3.1_

- [x] 6. Phase 5: Conflict Resolution Enhancement (冲突解决增强)
  - [x] 6.1 Create ConflictResolver class
    - Create `backend/src/modules/secretary/services/conflict_resolver.py`
    - Define ResolutionOption data model
    - Implement base `resolve_conflict()` method
    - _Requirements: 4.1_
  
  - [x] 6.2 Implement adjustability analysis
    - Implement `_analyze_adjustability()` method
    - Classify events as hard_constraint, soft_constraint, flexible
    - Based on event type, status, importance
    - _Requirements: 4.1_
  
  - [x] 6.3 Write property test for adjustability analysis
    - **Property 12: Conflict Adjustability Analysis**
    - **Validates: Requirements 4.1**
  
  - [x] 6.4 Implement resolution option generation
    - Generate time adjustment options (before, after, next day)
    - Generate cancellation options (if not hard constraint)
    - Each option includes reason and impact analysis
    - _Requirements: 4.2_
  
  - [x] 6.5 Write property test for multiple resolution options
    - **Property 13: Multiple Resolution Options Generation**
    - **Validates: Requirements 4.2**
  
  - [x] 6.6 Implement resolution option scoring
    - Score based on importance, urgency, opportunity cost
    - Lower-impact options score higher
    - Sort options by score
    - _Requirements: 4.3_
  
  - [x] 6.7 Write property test for resolution scoring
    - **Property 14: Resolution Option Scoring**
    - **Validates: Requirements 4.3**
  
  - [x] 6.8 Implement cascading conflict detection
    - Check if proposed adjustment creates new conflicts
    - Implement `_check_no_new_conflicts()` method
    - Only recommend adjustments that don't create new conflicts
    - _Requirements: 4.4_
  
  - [x] 6.9 Write property test for cascading conflict detection
    - **Property 15: Cascading Conflict Detection**
    - **Validates: Requirements 4.4**
  
  - [x] 6.10 Implement impact analysis
    - Analyze time change impact
    - Analyze association impact
    - Analyze trip impact (if event belongs to trip)
    - Generate impact_analysis string
    - _Requirements: 4.2_
  
  - [x] 6.11 Implement unresolvable conflict explanation
    - Detect when no resolution options are feasible
    - Generate clear explanation of why
    - Specify what user decision is needed
    - _Requirements: 4.5_
  
  - [x] 6.12 Write property test for unresolvable conflict explanation
    - **Property 16: Unresolvable Conflict Explanation**
    - **Validates: Requirements 4.5**
  
  - [x] 6.13 Integrate ConflictResolver into curation service
    - Update `_detect_and_resolve_conflicts()` to use ConflictResolver
    - Generate resolution options for each conflict
    - Attach options to ConflictAlert responses
    - _Requirements: 4.1_

- [x] 7. Checkpoint - Ensure context enrichment and conflict resolution tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 8. Phase 6: Briefing Generation (简报生成)
  - [x] 8.1 Create BriefingGenerator class
    - Create `backend/src/modules/secretary/services/briefing_generator.py`
    - Define DailyBriefing and BriefingItem data models
    - Implement base `generate_daily_briefing()` method
    - _Requirements: 5.1_
  
  - [x] 8.2 Implement importance-based event sorting
    - Implement `_sort_by_importance()` method
    - Score based on priority, urgency, opportunity cost, association count
    - Sort events by importance score (not chronological)
    - _Requirements: 5.1_
  
  - [x] 8.3 Write property test for importance-based ordering
    - **Property 17: Briefing Importance-Based Ordering**
    - **Validates: Requirements 5.1**
  
  - [x] 8.4 Implement key insights generation using LLM
    - Create INSIGHT_GENERATION_PROMPT
    - Collect context (events, historical events, social intents, stale contacts)
    - Call LLM to generate 2-3 key insights
    - Parse and return insights
    - _Requirements: 5.3_
  
  - [x] 8.5 Write property test for insight generation
    - **Property 19: Briefing Insight Generation**
    - **Validates: Requirements 5.3**
  
  - [x] 8.6 Implement opportunity discovery for briefing
    - Check for triggered social intents
    - Check for stale contacts in event locations
    - Check for important dates nearby
    - Generate opportunity reminders
    - _Requirements: 5.2, 5.4_
  
  - [x] 8.7 Write property test for social intent reminder
    - **Property 18: Briefing Social Intent Reminder**
    - **Validates: Requirements 5.2**
  
  - [x] 8.8 Write property test for important date preparation
    - **Property 20: Briefing Important Date Preparation**
    - **Validates: Requirements 5.4, 5.5**
  
  - [x] 8.9 Implement conflict detection with solutions for briefing
    - Detect conflicts in briefing period
    - Generate resolution suggestions using ConflictResolver
    - Include both conflict description and suggestions
    - _Requirements: 5.6_
  
  - [x] 8.10 Write property test for briefing conflict resolution
    - **Property 21: Briefing Conflict Resolution**
    - **Validates: Requirements 5.6**
  
  - [x] 8.11 Implement relationship reminders
    - Find stale contacts (>90 days no interaction)
    - Generate reminders with suggested contact timing
    - _Requirements: 5.5_
  
  - [x] 8.12 Create briefing API endpoint
    - Add GET /api/secretary/briefing endpoint
    - Accept date parameter (default: today)
    - Return DailyBriefing response
    - _Requirements: 5.1_

- [ ] 9. Phase 7: Event Graph and Timeline Enhancements (图谱和时光轴增强)
  - [x] 9.1 Implement event graph layering
    - Classify events into 4 layers: core trips, must-do, convenient, background
    - Based on event type and associations
    - Update `get_curated_graph()` response to include layer information
    - _Requirements: 6.1, 6.3, 6.4, 6.5_
  
  - [x] 9.2 Write property test for event graph layering
    - **Property 22: Event Graph Layering**
    - **Validates: Requirements 6.1, 6.3, 6.4, 6.5**
  
  - [x] 9.3 Enhance graph response with full context
    - Include enriched context for core event
    - Include all associations with full details
    - _Requirements: 6.6_
  
  - [x] 9.4 Write property test for graph association display
    - **Property 23: Event Graph Association Display**
    - **Validates: Requirements 6.6**
  
  - [x] 9.5 Implement timeline event grouping
    - Group events by trip_id
    - Add trip theme label to grouped events
    - _Requirements: 7.2_
  
  - [x] 9.6 Write property test for timeline grouping
    - **Property 24: Timeline Event Grouping**
    - **Validates: Requirements 7.2**
  
  - [x] 9.7 Add dependency relationship data to timeline
    - Include related_events from context
    - Add dependency indicators
    - _Requirements: 7.3, 7.4_
  
  - [x] 9.8 Write property test for timeline dependency display
    - **Property 25: Timeline Dependency Display**
    - **Validates: Requirements 7.3, 7.4**
  
  - [x] 9.9 Add conflict highlighting to timeline
    - Mark conflicting events
    - Include resolution suggestions
    - _Requirements: 7.5_
  
  - [x] 9.10 Write property test for timeline conflict highlighting
    - **Property 26: Timeline Conflict Highlighting**
    - **Validates: Requirements 7.5**

- [ ] 10. Phase 8: Performance Optimization (性能优化)
  - [x] 10.1 Implement memory query caching
    - Add Redis cache for frequent memory queries
    - Cache key: (family_id, context_hash)
    - TTL: 5 minutes
    - _Requirements: 8.1_
  
  - [x] 10.2 Implement incremental association computation
    - Track last_processed_at timestamp for events
    - Only process new/modified events
    - _Requirements: 8.2_
  
  - [x] 10.3 Write property test for incremental computation
    - **Property 27: Incremental Association Computation**
    - **Validates: Requirements 8.2**
  
  - [x] 10.4 Implement async briefing generation
    - Make briefing generation fully async
    - Use asyncio.gather for parallel queries
    - _Requirements: 8.3_
  
  - [x] 10.5 Add database query indexes
    - Add index on social_intents(trigger_location, status)
    - Add index on curated_events(location, normalized_start)
    - Add index on conversation_memories(family_id, created_at)
    - _Requirements: 8.1_
  
  - [x] 10.6 Implement performance guard with timeouts
    - Create PerformanceGuard class
    - Implement `query_with_timeout()` method
    - Set 5s timeout for memory queries
    - Return default values on timeout
    - _Requirements: 8.1_

- [ ] 11. Phase 9: Backward Compatibility and Error Isolation (向后兼容和错误隔离)
  - [x] 11.1 Test backward compatibility with existing data
    - Load existing CuratedEvent records
    - Verify new code can process them
    - _Requirements: 9.1_
  
  - [x] 11.2 Write property test for backward compatibility
    - **Property 29: Backward Compatibility**
    - **Validates: Requirements 9.1, 9.3**
  
  - [x] 11.3 Implement error isolation for new features
    - Wrap new intelligence features in try-catch
    - Log errors but don't fail core curation
    - Return default/empty values on feature failure
    - _Requirements: 9.5_
  
  - [x] 11.4 Write property test for error isolation
    - **Property 30: Error Isolation**
    - **Validates: Requirements 9.5**
  
  - [x] 11.5 Create data migration script for social_intents
    - Extract social intents from existing ConversationMemory records
    - Populate social_intents table
    - Verify migration results
    - _Requirements: 9.4_
  
  - [x] 11.6 Implement LLM output validation
    - Create JSON schemas for LLM responses
    - Validate association discovery output
    - Validate insight generation output
    - Reject malformed responses
    - _Requirements: 10.5_
  
  - [x] 11.7 Write property test for LLM output validation
    - **Property 31: LLM Output Structure Validation**
    - **Validates: Requirements 10.2, 10.3, 10.5**

- [x] 12. Final Checkpoint - Integration testing and deployment
  - Run full integration test suite
  - Verify all property tests pass (100+ iterations each)
  - Performance test with realistic data volumes
  - Deploy to staging environment
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional property-based tests and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties (using hypothesis library, 100+ iterations)
- Unit tests validate specific examples and edge cases
- Integration tests verify end-to-end workflows
