import '../../../../core/utils/timezone_utils.dart';

/// Memory model for secretary memories
class MemoryModel {
  final String id;
  final String memoryType;
  final String content;
  final String summary;
  final Map<String, dynamic>? entities;
  final List<String> tags;
  final int importance;
  final double confidence;
  final String status;
  final DateTime createdAt;
  final DateTime? expiresAt;
  final int recallCount;

  const MemoryModel({
    required this.id,
    required this.memoryType,
    required this.content,
    required this.summary,
    this.entities,
    this.tags = const [],
    this.importance = 5,
    this.confidence = 0.8,
    this.status = 'active',
    required this.createdAt,
    this.expiresAt,
    this.recallCount = 0,
  });

  factory MemoryModel.fromJson(Map<String, dynamic> json) {
    return MemoryModel(
      id: json['id'] as String,
      memoryType: json['memory_type'] as String? ?? 'general',
      content: json['content'] as String,
      summary: json['summary'] as String? ?? json['content'] as String,
      entities: json['entities'] as Map<String, dynamic>?,
      tags: (json['tags'] as List<dynamic>?)?.cast<String>() ?? const [],
      importance: json['importance'] as int? ?? 5,
      confidence: (json['confidence'] as num?)?.toDouble() ?? 0.8,
      status: json['status'] as String? ?? 'active',
      createdAt: TimezoneUtils.parseApiTime(json['created_at'] as String),
      expiresAt: json['expires_at'] != null
          ? TimezoneUtils.parseApiTime(json['expires_at'] as String)
          : null,
      recallCount: json['recall_count'] as int? ?? 0,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'memory_type': memoryType,
      'content': content,
      'summary': summary,
      'entities': entities,
      'tags': tags,
      'importance': importance,
      'confidence': confidence,
      'status': status,
      'created_at': TimezoneUtils.toApiTime(createdAt),
      'expires_at': expiresAt != null ? TimezoneUtils.toApiTime(expiresAt!) : null,
      'recall_count': recallCount,
    };
  }

  /// Get person from entities
  String? get person => entities?['person'] as String?;

  /// Get location from entities
  String? get location => entities?['location'] as String?;

  /// Get time hint from entities
  String? get timeHint => entities?['time_hint'] as String?;

  /// Check if memory is active
  bool get isActive => status == 'active';

  /// Check if memory is high importance
  bool get isHighImportance => importance >= 7;

  /// Get type icon based on memory type
  String get typeIcon {
    switch (memoryType) {
      case 'emotion':
        return '💭';
      case 'plan':
        return '📋';
      case 'schedule':
        return '📅';
      case 'relationship':
        return '👥';
      case 'preference':
        return '❤️';
      case 'life_event':
        return '🎉';
      case 'location':
        return '📍';
      case 'health':
        return '🏥';
      default:
        return '📝';
    }
  }

  /// Get display name for memory type
  String get typeDisplayName {
    switch (memoryType) {
      case 'emotion':
        return '情感';
      case 'plan':
        return '计划';
      case 'schedule':
        return '日程';
      case 'relationship':
        return '关系';
      case 'preference':
        return '偏好';
      case 'life_event':
        return '事件';
      case 'location':
        return '地点';
      case 'health':
        return '健康';
      default:
        return '记忆';
    }
  }

  /// Get relative time text (uses local time for comparison)
  String get timeAgoText {
    final now = DateTime.now();
    final localCreatedAt = createdAt.toLocal();
    final diff = now.difference(localCreatedAt);

    if (diff.inDays > 365) {
      return '${(diff.inDays / 365).floor()}年前';
    } else if (diff.inDays > 30) {
      return '${(diff.inDays / 30).floor()}个月前';
    } else if (diff.inDays > 7) {
      return '${(diff.inDays / 7).floor()}周前';
    } else if (diff.inDays > 0) {
      return '${diff.inDays}天前';
    } else if (diff.inHours > 0) {
      return '${diff.inHours}小时前';
    } else if (diff.inMinutes > 0) {
      return '${diff.inMinutes}分钟前';
    } else {
      return '刚刚';
    }
  }
}

/// Result from context check API
class ContextCheckResult {
  final InsightModel? insight;
  final List<MemoryModel> relatedMemories;

  const ContextCheckResult({
    this.insight,
    this.relatedMemories = const [],
  });

  factory ContextCheckResult.fromJson(Map<String, dynamic> json) {
    return ContextCheckResult(
      insight: json['insight'] != null
          ? InsightModel.fromJson(json['insight'] as Map<String, dynamic>)
          : null,
      relatedMemories: (json['related_memories'] as List<dynamic>?)
              ?.map((e) => MemoryModel.fromJson(e as Map<String, dynamic>))
              .toList() ??
          const [],
    );
  }

  bool get hasInsight => insight != null;
}

/// Insight model for AI-generated insights
class InsightModel {
  final String id;
  final String insightType;
  final String title;
  final String content;
  final int priority;
  final String urgency;
  final String status;
  final List<String> actionOptions;
  final Map<String, dynamic>? actionData;
  final List<String>? relatedMemoryIds;
  final List<String>? relatedTravelIds;
  final DateTime createdAt;
  final DateTime? expiresAt;

  const InsightModel({
    required this.id,
    required this.insightType,
    required this.title,
    required this.content,
    this.priority = 5,
    this.urgency = 'normal',
    this.status = 'active',
    this.actionOptions = const [],
    this.actionData,
    this.relatedMemoryIds,
    this.relatedTravelIds,
    required this.createdAt,
    this.expiresAt,
  });

  factory InsightModel.fromJson(Map<String, dynamic> json) {
    return InsightModel(
      id: json['id'] as String,
      insightType: json['insight_type'] as String? ?? 'general',
      title: json['title'] as String,
      content: json['content'] as String,
      priority: json['priority'] as int? ?? 5,
      urgency: json['urgency'] as String? ?? 'normal',
      status: json['status'] as String? ?? 'active',
      actionOptions: (json['action_options'] as List<dynamic>?)?.cast<String>() ?? const [],
      actionData: json['action_data'] as Map<String, dynamic>?,
      relatedMemoryIds: (json['related_memory_ids'] as List<dynamic>?)?.cast<String>(),
      relatedTravelIds: (json['related_travel_ids'] as List<dynamic>?)?.cast<String>(),
      createdAt: TimezoneUtils.parseApiTime(json['created_at'] as String),
      expiresAt: json['expires_at'] != null
          ? TimezoneUtils.parseApiTime(json['expires_at'] as String)
          : null,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'insight_type': insightType,
      'title': title,
      'content': content,
      'priority': priority,
      'urgency': urgency,
      'status': status,
      'action_options': actionOptions,
      'action_data': actionData,
      'related_memory_ids': relatedMemoryIds,
      'related_travel_ids': relatedTravelIds,
      'created_at': TimezoneUtils.toApiTime(createdAt),
      'expires_at': expiresAt != null ? TimezoneUtils.toApiTime(expiresAt!) : null,
    };
  }

  bool get isHighPriority => priority >= 7;

  bool get isUrgent => urgency == 'high';

  bool get isActive => status == 'active';

  String get typeIcon {
    switch (insightType) {
      case 'reminder':
        return '⏰';
      case 'suggestion':
        return '💡';
      case 'observation':
        return '👁️';
      case 'correlation':
        return '🔗';
      default:
        return '📌';
    }
  }

  String get typeDisplayName {
    switch (insightType) {
      case 'reminder':
        return '提醒';
      case 'suggestion':
        return '建议';
      case 'observation':
        return '观察';
      case 'correlation':
        return '关联';
      default:
        return '洞察';
    }
  }
}
