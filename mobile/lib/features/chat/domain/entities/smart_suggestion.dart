import 'package:equatable/equatable.dart';

/// Types of smart suggestions
enum SuggestionType {
  locationCorrelation,
  timeCorrelation,
  personCorrelation,
  historyCorrelation,
  preparationReminder,
  anniversaryReminder,
  giftReminder,
  meetupSuggestion,
}

/// Urgency levels for suggestions
enum SuggestionUrgency {
  high,
  normal,
  low,
}

/// Smart suggestion entity
class SmartSuggestion extends Equatable {
  final String id;
  final SuggestionType type;
  final String title;
  final String content;
  final String icon;
  final List<String> relatedEventIds;
  final List<String> relatedMemberIds;
  final List<String> relatedTravelIds;
  final List<String> actionOptions;
  final Map<String, dynamic> actionData;
  final int priority;
  final SuggestionUrgency urgency;
  final DateTime? expiresAt;
  final DateTime createdAt;

  const SmartSuggestion({
    required this.id,
    required this.type,
    required this.title,
    required this.content,
    this.icon = 'lightbulb',
    this.relatedEventIds = const [],
    this.relatedMemberIds = const [],
    this.relatedTravelIds = const [],
    this.actionOptions = const [],
    this.actionData = const {},
    this.priority = 0,
    this.urgency = SuggestionUrgency.normal,
    this.expiresAt,
    required this.createdAt,
  });

  /// Get icon data based on icon name
  String get iconName {
    switch (icon) {
      case 'luggage':
        return 'luggage';
      case 'flight_takeoff':
        return 'flight_takeoff';
      case 'event':
        return 'event';
      case 'people':
        return 'people';
      case 'cake':
        return 'cake';
      case 'favorite':
        return 'favorite';
      case 'event_note':
        return 'event_note';
      case 'location_on':
        return 'location_on';
      case 'person':
        return 'person';
      case 'schedule':
        return 'schedule';
      case 'history':
        return 'history';
      default:
        return 'lightbulb';
    }
  }

  /// Get type display name
  String get typeName {
    switch (type) {
      case SuggestionType.preparationReminder:
        return '行前准备';
      case SuggestionType.locationCorrelation:
        return '地点关联';
      case SuggestionType.meetupSuggestion:
        return '见面建议';
      case SuggestionType.personCorrelation:
        return '人物关联';
      case SuggestionType.giftReminder:
        return '礼物提醒';
      case SuggestionType.anniversaryReminder:
        return '纪念日提醒';
      case SuggestionType.timeCorrelation:
        return '时间关联';
      case SuggestionType.historyCorrelation:
        return '历史关联';
    }
  }

  /// Check if suggestion is expired
  bool get isExpired {
    if (expiresAt == null) return false;
    return DateTime.now().isAfter(expiresAt!);
  }

  /// Check if suggestion is high urgency
  bool get isHighUrgency => urgency == SuggestionUrgency.high;

  /// Get localized action name
  static String getActionName(String action) {
    switch (action) {
      case 'schedule_meeting':
        return '约见面';
      case 'send_message':
        return '发消息';
      case 'prepare_gift':
        return '准备礼物';
      case 'book_restaurant':
        return '预订餐厅';
      case 'set_reminder':
        return '设置提醒';
      case 'ignore':
        return '忽略';
      case 'view_details':
        return '查看详情';
      default:
        return action;
    }
  }

  SmartSuggestion copyWith({
    String? id,
    SuggestionType? type,
    String? title,
    String? content,
    String? icon,
    List<String>? relatedEventIds,
    List<String>? relatedMemberIds,
    List<String>? relatedTravelIds,
    List<String>? actionOptions,
    Map<String, dynamic>? actionData,
    int? priority,
    SuggestionUrgency? urgency,
    DateTime? expiresAt,
    DateTime? createdAt,
  }) {
    return SmartSuggestion(
      id: id ?? this.id,
      type: type ?? this.type,
      title: title ?? this.title,
      content: content ?? this.content,
      icon: icon ?? this.icon,
      relatedEventIds: relatedEventIds ?? this.relatedEventIds,
      relatedMemberIds: relatedMemberIds ?? this.relatedMemberIds,
      relatedTravelIds: relatedTravelIds ?? this.relatedTravelIds,
      actionOptions: actionOptions ?? this.actionOptions,
      actionData: actionData ?? this.actionData,
      priority: priority ?? this.priority,
      urgency: urgency ?? this.urgency,
      expiresAt: expiresAt ?? this.expiresAt,
      createdAt: createdAt ?? this.createdAt,
    );
  }

  @override
  List<Object?> get props => [
        id,
        type,
        title,
        content,
        icon,
        relatedEventIds,
        relatedMemberIds,
        relatedTravelIds,
        actionOptions,
        actionData,
        priority,
        urgency,
        expiresAt,
        createdAt,
      ];
}
