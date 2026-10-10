import '../../domain/entities/conflict_alert.dart';

/// ConflictAlert 数据模型 - 用于 API 通信
class ConflictAlertModel extends ConflictAlert {
  const ConflictAlertModel({
    required super.id,
    required super.title,
    super.description,
    required super.alertType,
    required super.priority,
    super.suggestedAction,
    super.relatedDate,
    super.relatedEventId,
    super.conflictingEventIds,
    super.metadata,
    super.pendingActionId,
    super.autoResolved,
    super.resolutionNote,
  });

  /// 从 JSON 创建模型
  factory ConflictAlertModel.fromJson(Map<String, dynamic> json) {
    final eventIds = (json['conflicting_event_ids'] as List<dynamic>?)
        ?.whereType<String>()
        .toList() ?? const [];
    return ConflictAlertModel(
      id: json['id'] as String,
      title: json['title'] as String,
      description: json['description'] as String?,
      alertType: _parseAlertType(json['alert_type'] as String?),
      priority: _parsePriority(json['priority'] as String?),
      suggestedAction: json['suggested_action'] as String?,
      relatedDate: json['related_date'] != null
          ? DateTime.parse(json['related_date'] as String)
          : null,
      relatedEventId: json['related_event_id'] as String?,
      conflictingEventIds: eventIds,
      metadata: json['metadata'] as Map<String, dynamic>?,
      pendingActionId: json['pending_action_id'] as String?,
      autoResolved: json['auto_resolved'] as bool? ?? false,
      resolutionNote: json['resolution_note'] as String?,
    );
  }

  /// 转换为 JSON
  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'title': title,
      'description': description,
      'alert_type': _alertTypeToString(alertType),
      'priority': _priorityToString(priority),
      'suggested_action': suggestedAction,
      'related_date': relatedDate?.toIso8601String(),
      'related_event_id': relatedEventId,
      'conflicting_event_ids': conflictingEventIds,
      'metadata': metadata,
      'pending_action_id': pendingActionId,
      'auto_resolved': autoResolved,
      'resolution_note': resolutionNote,
    };
  }

  /// 从实体创建模型
  factory ConflictAlertModel.fromEntity(ConflictAlert entity) {
    return ConflictAlertModel(
      id: entity.id,
      title: entity.title,
      description: entity.description,
      alertType: entity.alertType,
      priority: entity.priority,
      suggestedAction: entity.suggestedAction,
      relatedDate: entity.relatedDate,
      relatedEventId: entity.relatedEventId,
      conflictingEventIds: entity.conflictingEventIds,
      metadata: entity.metadata,
      pendingActionId: entity.pendingActionId,
      autoResolved: entity.autoResolved,
      resolutionNote: entity.resolutionNote,
    );
  }

  static AlertType _parseAlertType(String? type) {
    switch (type) {
      case 'date_conflict':
        return AlertType.dateConflict;
      case 'time_sensitive':
        return AlertType.timeSensitive;
      case 'reminder':
        return AlertType.reminder;
      case 'warning':
        return AlertType.warning;
      default:
        return AlertType.reminder;
    }
  }

  static String _alertTypeToString(AlertType type) {
    switch (type) {
      case AlertType.dateConflict:
        return 'date_conflict';
      case AlertType.timeSensitive:
        return 'time_sensitive';
      case AlertType.reminder:
        return 'reminder';
      case AlertType.warning:
        return 'warning';
    }
  }

  static AlertPriority _parsePriority(String? priority) {
    switch (priority) {
      case 'high':
        return AlertPriority.high;
      case 'medium':
        return AlertPriority.medium;
      case 'low':
        return AlertPriority.low;
      default:
        return AlertPriority.medium;
    }
  }

  static String _priorityToString(AlertPriority priority) {
    switch (priority) {
      case AlertPriority.high:
        return 'high';
      case AlertPriority.medium:
        return 'medium';
      case AlertPriority.low:
        return 'low';
    }
  }
}
