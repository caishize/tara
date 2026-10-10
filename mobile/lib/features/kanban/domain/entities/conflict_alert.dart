import 'package:equatable/equatable.dart';

/// 提醒类型枚举
enum AlertType {
  dateConflict,     // 日期冲突
  timeSensitive,    // 时间敏感
  reminder,         // 一般提醒
  warning,          // 警告
}

/// 提醒优先级
enum AlertPriority {
  high,    // 高优先级
  medium,  // 中优先级
  low,     // 低优先级
}

/// 冲突/提醒实体 - 需要注意的事项
class ConflictAlert extends Equatable {
  final String id;
  final String title;
  final String? description;
  final AlertType alertType;
  final AlertPriority priority;
  final String? suggestedAction;   // 建议的操作
  final DateTime? relatedDate;     // 相关日期
  final String? relatedEventId;    // 关联的事件ID (first from conflictingEventIds)
  final List<String> conflictingEventIds;  // 所有冲突事件ID
  final Map<String, dynamic>? metadata;
  final String? pendingActionId;   // 关联的待确认操作ID (需用户确认时)
  final bool autoResolved;         // 是否已被秘书自动处理
  final String? resolutionNote;    // 处理说明 (如 "已自动调整XX至YY后")

  const ConflictAlert({
    required this.id,
    required this.title,
    this.description,
    required this.alertType,
    required this.priority,
    this.suggestedAction,
    this.relatedDate,
    this.relatedEventId,
    this.conflictingEventIds = const [],
    this.metadata,
    this.pendingActionId,
    this.autoResolved = false,
    this.resolutionNote,
  });

  /// 获取提醒类型的中文显示名称
  String get alertTypeDisplayName {
    switch (alertType) {
      case AlertType.dateConflict:
        return '日期冲突';
      case AlertType.timeSensitive:
        return '时间敏感';
      case AlertType.reminder:
        return '提醒';
      case AlertType.warning:
        return '警告';
    }
  }

  /// 获取优先级的中文显示名称
  String get priorityDisplayName {
    switch (priority) {
      case AlertPriority.high:
        return '高';
      case AlertPriority.medium:
        return '中';
      case AlertPriority.low:
        return '低';
    }
  }

  /// 是否是高优先级
  bool get isHighPriority => priority == AlertPriority.high;

  /// 是否是冲突类型
  bool get isConflict => alertType == AlertType.dateConflict;

  /// 是否有建议操作
  bool get hasSuggestedAction =>
      suggestedAction != null && suggestedAction!.isNotEmpty;

  /// 是否需要用户确认
  bool get needsUserConfirm =>
      pendingActionId != null && !autoResolved;

  /// 创建副本
  ConflictAlert copyWith({
    String? id,
    String? title,
    String? description,
    AlertType? alertType,
    AlertPriority? priority,
    String? suggestedAction,
    DateTime? relatedDate,
    String? relatedEventId,
    List<String>? conflictingEventIds,
    Map<String, dynamic>? metadata,
    String? pendingActionId,
    bool? autoResolved,
    String? resolutionNote,
  }) {
    return ConflictAlert(
      id: id ?? this.id,
      title: title ?? this.title,
      description: description ?? this.description,
      alertType: alertType ?? this.alertType,
      priority: priority ?? this.priority,
      suggestedAction: suggestedAction ?? this.suggestedAction,
      relatedDate: relatedDate ?? this.relatedDate,
      relatedEventId: relatedEventId ?? this.relatedEventId,
      conflictingEventIds: conflictingEventIds ?? this.conflictingEventIds,
      metadata: metadata ?? this.metadata,
      pendingActionId: pendingActionId ?? this.pendingActionId,
      autoResolved: autoResolved ?? this.autoResolved,
      resolutionNote: resolutionNote ?? this.resolutionNote,
    );
  }

  @override
  List<Object?> get props => [
        id,
        title,
        description,
        alertType,
        priority,
        suggestedAction,
        relatedDate,
        relatedEventId,
        conflictingEventIds,
        metadata,
        pendingActionId,
        autoResolved,
        resolutionNote,
      ];
}
