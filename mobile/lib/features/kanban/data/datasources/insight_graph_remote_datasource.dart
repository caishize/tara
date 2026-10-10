import '../../../../core/network/api_client.dart';
import '../../domain/entities/associated_item.dart';
import '../../domain/entities/conflict_alert.dart';
import '../../domain/entities/core_event.dart';
import '../../domain/entities/insight_graph_data.dart';
import '../models/associated_item_model.dart';
import '../models/conflict_alert_model.dart';
import '../models/core_event_model.dart';

/// 行程摘要
class TripSummary {
  final String id;
  final String title;
  final DateTime startDate;
  final DateTime endDate;
  final String? location;
  final String priority;
  final String status;
  final int eventCount;
  final bool isCurrent;

  TripSummary({
    required this.id,
    required this.title,
    required this.startDate,
    required this.endDate,
    this.location,
    this.priority = 'normal',
    this.status = 'upcoming',
    this.eventCount = 0,
    this.isCurrent = false,
  });

  factory TripSummary.fromJson(Map<String, dynamic> json) {
    return TripSummary(
      id: json['id'] as String,
      title: json['title'] as String,
      startDate: DateTime.parse(json['start_date'] as String),
      endDate: DateTime.parse(json['end_date'] as String),
      location: json['location'] as String?,
      priority: json['priority'] as String? ?? 'normal',
      status: json['status'] as String? ?? 'upcoming',
      eventCount: json['event_count'] as int? ?? 0,
      isCurrent: json['is_current'] as bool? ?? false,
    );
  }
}

/// 图谱节点
class GraphNode {
  final String id;
  final String type;
  final String label;
  final String? icon;
  final String? status;
  final Map<String, dynamic>? data;
  final List<String> availableActions;

  GraphNode({
    required this.id,
    required this.type,
    required this.label,
    this.icon,
    this.status,
    this.data,
    this.availableActions = const [],
  });

  factory GraphNode.fromJson(Map<String, dynamic> json) {
    return GraphNode(
      id: json['id'] as String,
      type: json['type'] as String,
      label: json['label'] as String,
      icon: json['icon'] as String?,
      status: json['status'] as String?,
      data: json['data'] as Map<String, dynamic>?,
      availableActions: (json['available_actions'] as List<dynamic>?)
              ?.map((e) => e as String)
              .toList() ??
          [],
    );
  }
}

/// 图谱边
class GraphEdge {
  final String source;
  final String target;
  final String type;

  GraphEdge({
    required this.source,
    required this.target,
    required this.type,
  });

  factory GraphEdge.fromJson(Map<String, dynamic> json) {
    return GraphEdge(
      source: json['source'] as String,
      target: json['target'] as String,
      type: json['type'] as String,
    );
  }
}

/// 事件图谱响应
class EventGraphResponse {
  final TripSummary trip;
  final List<GraphNode> nodes;
  final List<GraphEdge> edges;
  final List<Map<String, dynamic>> events;

  EventGraphResponse({
    required this.trip,
    required this.nodes,
    required this.edges,
    required this.events,
  });

  factory EventGraphResponse.fromJson(Map<String, dynamic> json) {
    final nodesJson = json['nodes'] as List<dynamic>? ?? [];
    final edgesJson = json['edges'] as List<dynamic>? ?? [];
    final eventsJson = json['events'] as List<dynamic>? ?? [];

    return EventGraphResponse(
      trip: TripSummary.fromJson(json['trip'] as Map<String, dynamic>),
      nodes: nodesJson.map((n) => GraphNode.fromJson(n as Map<String, dynamic>)).toList(),
      edges: edgesJson.map((e) => GraphEdge.fromJson(e as Map<String, dynamic>)).toList(),
      events: eventsJson.map((e) => e as Map<String, dynamic>).toList(),
    );
  }
}

/// 动态图谱远程数据源
abstract class InsightGraphRemoteDataSource {
  /// 获取动态图谱数据
  Future<InsightGraphData?> fetchInsightGraph({DateTime? targetDate});

  /// 获取特定事件的动态图谱
  Future<InsightGraphData?> fetchInsightGraphForEvent(String eventId);

  /// 获取即将到来的行程列表
  Future<List<TripSummary>> fetchUpcomingTrips({int limit = 5});

  /// 获取行程的事件图谱
  Future<EventGraphResponse> fetchEventGraph(String tripId);

  /// 对事项执行操作
  Future<void> postItemAction(
    String itemId,
    String action, {
    String? correction,
    DateTime? scheduledStart,
  });

  /// 对提醒执行操作
  Future<void> postAlertAction(String alertId, String action);

  /// 创建关联
  Future<void> createAssociation({
    required String eventId,
    required String targetType,
    required String targetId,
    required String associationType,
    required String title,
    required String reason,
    String priority = 'convenient',
  });

  /// 确认待处理操作 (冲突解决)
  Future<Map<String, dynamic>> confirmPendingAction(
    String actionId, {
    DateTime? newStart,
    DateTime? newEnd,
  });

  /// 拒绝待处理操作 (冲突解决)
  Future<void> rejectPendingAction(String actionId);
}

/// 动态图谱远程数据源实现
class InsightGraphRemoteDataSourceImpl implements InsightGraphRemoteDataSource {
  final ApiClient _apiClient;

  InsightGraphRemoteDataSourceImpl({required ApiClient apiClient})
      : _apiClient = apiClient;

  @override
  Future<InsightGraphData?> fetchInsightGraph({DateTime? targetDate}) async {
    // 优先尝试使用新的 AI 整理后的图谱 API
    try {
      final curatedGraph = await _fetchCuratedGraph();
      if (curatedGraph != null) {
        return curatedGraph;
      }
    } catch (e) {
      // 新 API 失败，回退到旧方案
    }

    // 回退到原有的多 API 聚合方案
    return _fetchLegacyInsightGraph(targetDate: targetDate);
  }

  /// 从新的 AI 整理 API 获取图谱数据
  Future<InsightGraphData?> _fetchCuratedGraph({String? eventId}) async {
    try {
      final queryParams = <String, dynamic>{};
      if (eventId != null) {
        queryParams['event_id'] = eventId;
      }

      final response = await _apiClient.get<Map<String, dynamic>>(
        '/graph/curated-graph',
        queryParameters: queryParams.isEmpty ? null : queryParams,
      );

      return _parseCuratedGraphResponse(response);
    } catch (e) {
      return null;
    }
  }

  /// 解析 AI 整理后的图谱响应
  InsightGraphData? _parseCuratedGraphResponse(Map<String, dynamic> response) {
    final coreEventJson = response['core_event'] as Map<String, dynamic>?;
    if (coreEventJson == null) {
      return null;
    }

    // 解析核心事件
    final metadata = <String, dynamic>{
      ...(coreEventJson['metadata'] as Map<String, dynamic>? ?? const {}),
    };
    final tripId = coreEventJson['trip_id'] as String?;
    final tripName = coreEventJson['trip_name'] as String?;
    if (tripId != null && tripId.isNotEmpty) {
      metadata['trip_id'] = tripId;
    }
    if (tripName != null && tripName.isNotEmpty) {
      metadata['trip_name'] = tripName;
    }
    final coreEvent = CoreEventModel(
      id: coreEventJson['id'] as String? ?? '',
      title: _resolveCoreEventTitle(coreEventJson),
      subtitle: coreEventJson['dedup_reason'] as String? ?? '顺便可以做这些事...',
      location: coreEventJson['location'] as String?,
      startDate: _parseDateTime(coreEventJson['start_time']) ?? DateTime.now(),
      endDate: _parseDateTime(coreEventJson['end_time']),
      eventType: _parseEventType(coreEventJson['event_type'] as String?),
      metadata: metadata,
    );

    // 解析关联事项 (带 AI 生成的理由)
    final associationsJson = response['associations'] as List<dynamic>? ?? [];
    final associatedItems = associationsJson.map((a) {
      final assoc = a as Map<String, dynamic>;
      return AssociatedItemModel(
        id: assoc['id'] as String? ?? '',
        title: assoc['title'] as String? ?? '',
        subtitle: assoc['reason'] as String?,  // AI 生成的关联理由
        itemType: _mapTargetTypeToItemType(assoc['target_type'] as String?),
        priority: _mapAssociationPriority(assoc['priority'] as String?),
        contextHint: assoc['reason'] as String?,  // 显示 AI 理由作为上下文提示
        relatedMemberId: assoc['related_member_id'] as String?,
        metadata: assoc,
      );
    }).toList();

    // Parse conflicts from AI curation API
    final conflictsJson = response['conflicts'] as List<dynamic>? ?? [];
    final conflictAlerts = conflictsJson.map((c) {
      final conflict = c as Map<String, dynamic>;
      final eventIds = (conflict['conflicting_event_ids'] as List<dynamic>?)
          ?.whereType<String>()
          .toList() ?? const [];
      return ConflictAlertModel(
        id: conflict['id'] as String? ?? '',
        title: conflict['title'] as String? ?? '日程冲突',
        description: conflict['description'] as String?,
        alertType: AlertType.dateConflict,
        priority: _mapConflictPriority(conflict['priority'] as String?),
        suggestedAction: conflict['suggestion'] as String?,
        relatedEventId: eventIds.isNotEmpty ? eventIds.first : null,
        conflictingEventIds: eventIds,
        pendingActionId: conflict['pending_action_id'] as String?,
        autoResolved: conflict['auto_resolved'] as bool? ?? false,
        resolutionNote: conflict['resolution_note'] as String?,
      );
    }).toList();

    return InsightGraphData(
      coreEvent: coreEvent,
      associatedItems: associatedItems,
      conflictAlerts: conflictAlerts,
    );
  }

  /// 旧的多 API 聚合方案（作为回退）
  Future<InsightGraphData?> _fetchLegacyInsightGraph({DateTime? targetDate}) async {
    try {
      // 1. 获取日常简报来提取核心事件（出差、旅行等）
      final briefingResponse = await _apiClient.get<Map<String, dynamic>>(
        '/briefing/daily',
        queryParameters: targetDate != null
            ? {'date': _formatDate(targetDate)}
            : null,
      );

      // 2. 获取智能建议
      final suggestionsResponse = await _apiClient.get<Map<String, dynamic>>(
        '/briefing/suggestions',
        queryParameters: {'limit': 20},
      );

      // 3. 获取待处理的洞察
      final insightsResponse = await _apiClient.get<Map<String, dynamic>>(
        '/memory/insights',
        queryParameters: {'limit': 10},
      );

      // 解析并转换数据
      return _parseResponses(
        briefingResponse,
        suggestionsResponse,
        insightsResponse,
      );
    } catch (e) {
      // 如果 API 调用失败，返回 null（让 UI 显示空状态）
      return null;
    }
  }

  @override
  Future<InsightGraphData?> fetchInsightGraphForEvent(String eventId) async {
    // 优先尝试使用新的 AI 整理后的图谱 API
    try {
      final curatedGraph = await _fetchCuratedGraph(eventId: eventId);
      if (curatedGraph != null) {
        return curatedGraph;
      }
    } catch (e) {
      // 新 API 失败，回退到旧方案
    }

    // No legacy fallback — BLoC uses TripSummary to build synthetic data
    return null;
  }

  @override
  Future<void> postItemAction(
    String itemId,
    String action, {
    String? correction,
    DateTime? scheduledStart,
  }) async {
    // 根据 action 类型决定调用哪个 API
    // 首先尝试新的 association API
    if (action == 'dismiss') {
      try {
        await _apiClient.post<Map<String, dynamic>>(
          '/graph/associations/$itemId/dismiss',
          data: correction != null ? {'correction': correction} : null,
        );
        return;
      } catch (e) {
        // 新 API 失败，尝试旧 API
      }
      await _apiClient.post<Map<String, dynamic>>(
        '/briefing/suggestions/$itemId/dismiss',
      );
    } else if (action == 'confirm') {
      try {
        await _apiClient.post<Map<String, dynamic>>(
          '/graph/associations/$itemId/confirm',
          data: scheduledStart != null
              ? {'scheduled_start': scheduledStart.toUtc().toIso8601String()}
              : null,
        );
        return;
      } catch (e) {
        // 新 API 失败，尝试旧 API
      }
      await _apiClient.post<Map<String, dynamic>>(
        '/briefing/suggestions/action',
        data: {
          'suggestion_id': itemId,
          'action': action,
        },
      );
    } else {
      await _apiClient.post<Map<String, dynamic>>(
        '/briefing/suggestions/action',
        data: {
          'suggestion_id': itemId,
          'action': action,
        },
      );
    }
  }

  @override
  Future<void> postAlertAction(String alertId, String action) async {
    if (action == 'dismiss') {
      await _apiClient.post<Map<String, dynamic>>(
        '/memory/insights/$alertId/dismiss',
      );
    } else {
      await _apiClient.post<Map<String, dynamic>>(
        '/memory/insights/$alertId/action',
        data: {'action': action},
      );
    }
  }

  @override
  Future<List<TripSummary>> fetchUpcomingTrips({int limit = 5}) async {
    final response = await _apiClient.get<List<dynamic>>(
      '/trips/plans',
      queryParameters: {'limit': limit},
    );

    return response.map((t) => TripSummary.fromJson(t as Map<String, dynamic>)).toList();
  }

  @override
  Future<EventGraphResponse> fetchEventGraph(String tripId) async {
    final response = await _apiClient.get<Map<String, dynamic>>(
      '/graph/trip/$tripId',
    );

    return EventGraphResponse.fromJson(response);
  }

  @override
  Future<void> createAssociation({
    required String eventId,
    required String targetType,
    required String targetId,
    required String associationType,
    required String title,
    required String reason,
    String priority = 'convenient',
  }) async {
    await _apiClient.post<Map<String, dynamic>>(
      '/graph/associations',
      data: {
        'target_type': targetType,
        'target_id': targetId,
        'association_type': associationType,
        'title': title,
        'reason': reason,
        'priority': priority,
      },
    );
  }

  @override
  Future<Map<String, dynamic>> confirmPendingAction(
    String actionId, {
    DateTime? newStart,
    DateTime? newEnd,
  }) async {
    Map<String, dynamic>? data;
    if (newStart != null || newEnd != null) {
      final overrides = <String, dynamic>{};
      if (newStart != null) {
        overrides['new_start'] = newStart.toUtc().toIso8601String();
      }
      if (newEnd != null) {
        overrides['new_end'] = newEnd.toUtc().toIso8601String();
      }
      data = {'payload_overrides': overrides};
    }
    final response = await _apiClient.post<Map<String, dynamic>>(
      '/actions/$actionId/confirm',
      data: data,
    );
    return response;
  }

  @override
  Future<void> rejectPendingAction(String actionId) async {
    await _apiClient.post<Map<String, dynamic>>(
      '/actions/$actionId/reject',
    );
  }

  /// 从 target_type 映射到 ItemType
  ItemType _mapTargetTypeToItemType(String? targetType) {
    switch (targetType) {
      case 'person':
        return ItemType.person;
      case 'gift':
        return ItemType.gift;
      case 'place':
        return ItemType.place;
      case 'task':
        return ItemType.task;
      case 'date':
        return ItemType.task;  // 日期提醒归为任务类型
      case 'memory':
        return ItemType.task;  // 记忆关联归为任务类型
      default:
        return ItemType.task;
    }
  }

  /// 从 association priority 映射到 ItemPriority
  ItemPriority _mapAssociationPriority(String? priority) {
    switch (priority) {
      case 'strongly_recommend':
        return ItemPriority.stronglyRecommend;
      case 'convenient':
        return ItemPriority.convenient;
      case 'optional':
        return ItemPriority.optional;
      default:
        return ItemPriority.convenient;
    }
  }

  /// 从 conflict priority 映射到 AlertPriority
  AlertPriority _mapConflictPriority(String? priority) {
    switch (priority) {
      case 'high':
        return AlertPriority.high;
      case 'medium':
        return AlertPriority.medium;
      case 'low':
        return AlertPriority.low;
      default:
        return AlertPriority.high;
    }
  }

  /// Prefer trip_name over Day-level title (e.g. "Day 1 · 广州周末游" → "广州周末游")
  String _resolveCoreEventTitle(Map<String, dynamic> json) {
    final title = json['title'] as String? ?? '';
    final tripName = json['trip_name'] as String?;
    if (tripName != null &&
        tripName.isNotEmpty &&
        title.startsWith('Day ') &&
        title.contains(' · ')) {
      return tripName;
    }
    return title;
  }

  /// 解析事件类型
  EventType _parseEventType(String? type) {
    switch (type) {
      case 'business_trip':
        return EventType.businessTrip;
      case 'travel':
        return EventType.travel;
      case 'meeting':
        return EventType.meeting;
      case 'birthday':
      case 'anniversary':
      case 'holiday':
      case 'reminder':
      default:
        return EventType.other;
    }
  }

  /// 解析后端响应并转换为 InsightGraphData
  InsightGraphData? _parseResponses(
    Map<String, dynamic> briefing,
    Map<String, dynamic> suggestions,
    Map<String, dynamic> insights,
  ) {
    // 1. 从简报中提取核心事件（优先取旅行/出差事件）
    final coreEvent = _extractCoreEvent(briefing);
    if (coreEvent == null) {
      return null;
    }

    // 2. 将建议转换为关联事项
    final associatedItems = _convertSuggestionsToItems(
      suggestions['suggestions'] as List<dynamic>? ?? [],
    );

    // 3. 将洞察和冲突转换为提醒
    final conflictAlerts = _convertInsightsToAlerts(
      insights['insights'] as List<dynamic>? ?? [],
      briefing['conflicts'] as List<dynamic>? ?? [],
    );

    return InsightGraphData(
      coreEvent: coreEvent,
      associatedItems: associatedItems,
      conflictAlerts: conflictAlerts,
    );
  }

  /// 从日常简报中提取核心事件
  CoreEvent? _extractCoreEvent(Map<String, dynamic> briefing) {
    // 优先从即将到来的旅行中提取
    final upcomingTrips = briefing['upcoming_trips'] as List<dynamic>?;
    if (upcomingTrips != null && upcomingTrips.isNotEmpty) {
      final trip = upcomingTrips.first as Map<String, dynamic>;
      return CoreEventModel(
        id: trip['trip_id']?.toString() ?? 'trip-${DateTime.now().millisecondsSinceEpoch}',
        title: _buildTripTitle(trip),
        subtitle: '顺便可以做这些事...',
        location: trip['destination'] as String?,
        startDate: _parseDateTime(trip['start_date']) ?? DateTime.now(),
        endDate: _parseDateTime(trip['end_date']),
        eventType: _parseTripType(trip['trip_type'] as String?),
      );
    }

    // 从今日事件中提取
    final todayEvents = briefing['today_events'] as List<dynamic>?;
    if (todayEvents != null && todayEvents.isNotEmpty) {
      final event = todayEvents.first as Map<String, dynamic>;
      return CoreEventModel(
        id: event['id']?.toString() ?? 'event-${DateTime.now().millisecondsSinceEpoch}',
        title: event['title'] as String? ?? '今日事件',
        subtitle: event['description'] as String? ?? '相关的智能建议',
        location: event['location'] as String?,
        startDate: _parseDateTime(event['start_time']) ?? DateTime.now(),
        endDate: _parseDateTime(event['end_time']),
        eventType: EventType.other,
      );
    }

    // 如果没有具体事件，创建一个通用的"本周计划"事件
    final weekStart = DateTime.now();
    return CoreEventModel(
      id: 'week-${weekStart.millisecondsSinceEpoch}',
      title: '本周智能关联',
      subtitle: '基于您的日程和记忆生成的建议',
      startDate: weekStart,
      eventType: EventType.other,
    );
  }

  /// 构建旅行标题
  String _buildTripTitle(Map<String, dynamic> trip) {
    final destination = trip['destination'] as String? ?? '目的地';
    final tripType = trip['trip_type'] as String?;
    final startDate = _parseDateTime(trip['start_date']);

    String prefix = '';
    if (startDate != null) {
      final daysUntil = startDate.difference(DateTime.now()).inDays;
      if (daysUntil == 0) {
        prefix = '今天';
      } else if (daysUntil == 1) {
        prefix = '明天';
      } else if (daysUntil < 7) {
        prefix = _getWeekdayName(startDate);
      } else {
        prefix = '${daysUntil}天后';
      }
    }

    final action = tripType == 'business_trip' ? '出差' : '去';
    return '$prefix$action$destination';
  }

  /// 将后端建议转换为关联事项
  List<AssociatedItem> _convertSuggestionsToItems(List<dynamic> suggestions) {
    return suggestions.map((s) {
      final suggestion = s as Map<String, dynamic>;
      return AssociatedItemModel(
        id: suggestion['id'] as String? ?? '',
        title: suggestion['title'] as String? ?? '',
        subtitle: _extractSubtitle(suggestion),
        itemType: _mapSuggestionTypeToItemType(suggestion['type'] as String?),
        priority: _mapPriorityToItemPriority(suggestion['priority'] as int? ?? 0),
        contextHint: suggestion['content'] as String?,
        relatedMemberId: _extractFirstMemberId(suggestion['related_member_ids']),
        metadata: suggestion,
      );
    }).toList();
  }

  /// 将后端洞察转换为提醒
  List<ConflictAlert> _convertInsightsToAlerts(
    List<dynamic> insights,
    List<dynamic> conflicts,
  ) {
    final alerts = <ConflictAlert>[];

    // 转换洞察
    for (final i in insights) {
      final insight = i as Map<String, dynamic>;
      alerts.add(ConflictAlertModel(
        id: insight['id'] as String? ?? '',
        title: insight['title'] as String? ?? '',
        description: insight['content'] as String?,
        alertType: _mapInsightTypeToAlertType(insight['insight_type'] as String?),
        priority: _mapUrgencyToAlertPriority(insight['urgency'] as String?),
        suggestedAction: _extractSuggestedAction(insight['action_options']),
      ));
    }

    // 转换冲突
    for (final c in conflicts) {
      final conflict = c as Map<String, dynamic>;
      alerts.add(ConflictAlertModel(
        id: conflict['id']?.toString() ?? 'conflict-${DateTime.now().millisecondsSinceEpoch}',
        title: conflict['title'] as String? ?? '日程冲突',
        description: conflict['description'] as String?,
        alertType: AlertType.dateConflict,
        priority: AlertPriority.high,
        suggestedAction: conflict['suggestion'] as String?,
      ));
    }

    return alerts;
  }

  // ==================== 辅助方法 ====================

  String _formatDate(DateTime date) {
    return '${date.year}-${date.month.toString().padLeft(2, '0')}-${date.day.toString().padLeft(2, '0')}';
  }

  DateTime? _parseDateTime(dynamic value) {
    if (value == null) return null;
    if (value is DateTime) return value;
    if (value is String) {
      return DateTime.tryParse(value);
    }
    return null;
  }

  String _getWeekdayName(DateTime date) {
    const weekdays = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'];
    return weekdays[date.weekday % 7];
  }

  EventType _parseTripType(String? type) {
    switch (type) {
      case 'business_trip':
        return EventType.businessTrip;
      case 'leisure':
      case 'family':
      case 'visit':
        return EventType.travel;
      case 'conference':
      case 'client_visit':
        return EventType.meeting;
      default:
        return EventType.other;
    }
  }

  ItemType _mapSuggestionTypeToItemType(String? type) {
    switch (type) {
      case 'person_correlation':
      case 'meetup_suggestion':
        return ItemType.person;
      case 'gift_reminder':
      case 'anniversary_reminder':
        return ItemType.gift;
      case 'location_correlation':
        return ItemType.place;
      case 'business_meeting':
      case 'client_visit':
      case 'partner_meeting':
        return ItemType.business;
      case 'preparation_reminder':
      case 'time_correlation':
      case 'history_correlation':
      case 'memory_correlation':
      case 'plan_reminder':
      default:
        return ItemType.task;
    }
  }

  ItemPriority _mapPriorityToItemPriority(int priority) {
    if (priority >= 80) {
      return ItemPriority.stronglyRecommend;
    } else if (priority >= 50) {
      return ItemPriority.convenient;
    } else {
      return ItemPriority.optional;
    }
  }

  AlertType _mapInsightTypeToAlertType(String? type) {
    switch (type) {
      case 'reminder':
        return AlertType.reminder;
      case 'correlation':
        return AlertType.timeSensitive;
      case 'followup':
        return AlertType.reminder;
      default:
        return AlertType.reminder;
    }
  }

  AlertPriority _mapUrgencyToAlertPriority(String? urgency) {
    switch (urgency) {
      case 'high':
        return AlertPriority.high;
      case 'low':
        return AlertPriority.low;
      default:
        return AlertPriority.medium;
    }
  }

  String? _extractSubtitle(Map<String, dynamic> suggestion) {
    // 尝试从 action_data 中提取更多信息
    final actionData = suggestion['action_data'] as Map<String, dynamic>?;
    if (actionData != null) {
      final memberName = actionData['member_name'] as String?;
      final relationship = actionData['relationship'] as String?;
      if (memberName != null && relationship != null) {
        return '$relationship·$memberName';
      }
    }

    // 从 icon 推断类型
    final icon = suggestion['icon'] as String?;
    switch (icon) {
      case 'people':
        return '见面建议';
      case 'cake':
        return '生日提醒';
      case 'favorite':
        return '纪念日';
      case 'luggage':
        return '行前准备';
      default:
        return null;
    }
  }

  String? _extractFirstMemberId(dynamic memberIds) {
    if (memberIds is List && memberIds.isNotEmpty) {
      return memberIds.first?.toString();
    }
    return null;
  }

  String? _extractSuggestedAction(dynamic actionOptions) {
    if (actionOptions is List && actionOptions.isNotEmpty) {
      // 返回第一个非 ignore 的操作
      for (final action in actionOptions) {
        if (action != 'ignore' && action != 'view_details') {
          return _translateAction(action.toString());
        }
      }
    }
    return null;
  }

  String _translateAction(String action) {
    switch (action) {
      case 'schedule_meeting':
        return '安排见面';
      case 'send_message':
        return '发送消息';
      case 'prepare_gift':
        return '准备礼物';
      case 'book_restaurant':
        return '预订餐厅';
      case 'set_reminder':
        return '设置提醒';
      default:
        return action;
    }
  }
}
