import '../../../kanban/data/models/insight_feed_models.dart';

class MemberInsightModel {
  final String id;
  final String source; // "memory", "briefing", "association", "insight"
  final String insightType;
  final String title;
  final String content;
  final int? priority;
  final int? importance;
  final String? urgency;
  final String status;
  final DateTime createdAt;
  final Map<String, dynamic>? actionData;
  final String? suggestedAction;
  final List<ActionOptionModel> actionOptions;

  const MemberInsightModel({
    required this.id,
    required this.source,
    required this.insightType,
    required this.title,
    required this.content,
    this.priority,
    this.importance,
    this.urgency,
    required this.status,
    required this.createdAt,
    this.actionData,
    this.suggestedAction,
    this.actionOptions = const [],
  });

  factory MemberInsightModel.fromJson(Map<String, dynamic> json) {
    final options = ActionOptionModel.parseList(json['action_options']);

    return MemberInsightModel(
      id: json['id'] as String,
      source: json['source'] as String? ?? 'memory',
      insightType: json['insight_type'] as String? ?? 'general',
      title: json['title'] as String,
      content: json['content'] as String,
      priority: json['priority'] as int?,
      importance: json['importance'] as int?,
      urgency: json['urgency'] as String?,
      status: json['status'] as String? ?? 'active',
      createdAt: DateTime.parse(json['created_at'] as String),
      actionData: json['action_data'] as Map<String, dynamic>?,
      suggestedAction: json['suggested_action'] as String?,
      actionOptions: options,
    );
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

  /// Get source display text
  String get sourceText {
    switch (source) {
      case 'memory':
        return '记忆洞察';
      case 'briefing':
        return '日程洞察';
      case 'association':
        return '行程建议';
      case 'insight':
        return 'AI洞察';
      default:
        return '洞察';
    }
  }

  /// Whether this insight is high priority/urgent
  bool get isHighPriority {
    if (urgency == 'high' || urgency == 'critical') return true;
    if (priority != null && priority! >= 8) return true;
    if (importance != null && importance! >= 8) return true;
    return false;
  }

  /// Convert to unified [InsightFeedItemModel] for use with [InsightSection].
  InsightFeedItemModel toInsightFeedItem() {
    return InsightFeedItemModel(
      id: id,
      title: title,
      content: content,
      insightType: insightType,
      priority: priority ?? 5,
      urgency: urgency ?? 'normal',
      createdAt: createdAt,
      actionType: suggestedAction,
      actionData: actionData,
      actionOptions: actionOptions,
      sourceContext: sourceText,
    );
  }
}
