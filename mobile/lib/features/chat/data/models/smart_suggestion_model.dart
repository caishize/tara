import '../../../../core/utils/timezone_utils.dart';

import '../../domain/entities/smart_suggestion.dart';

/// Model for smart suggestion API responses
class SmartSuggestionModel extends SmartSuggestion {
  const SmartSuggestionModel({
    required super.id,
    required super.type,
    required super.title,
    required super.content,
    super.icon,
    super.relatedEventIds,
    super.relatedMemberIds,
    super.relatedTravelIds,
    super.actionOptions,
    super.actionData,
    super.priority,
    super.urgency,
    super.expiresAt,
    required super.createdAt,
  });

  factory SmartSuggestionModel.fromJson(Map<String, dynamic> json) {
    return SmartSuggestionModel(
      id: json['id'] as String,
      type: _parseType(json['type'] as String),
      title: json['title'] as String,
      content: json['content'] as String,
      icon: json['icon'] as String? ?? 'lightbulb',
      relatedEventIds: (json['related_event_ids'] as List<dynamic>?)
              ?.map((e) => e as String)
              .toList() ??
          [],
      relatedMemberIds: (json['related_member_ids'] as List<dynamic>?)
              ?.map((e) => e as String)
              .toList() ??
          [],
      relatedTravelIds: (json['related_travel_ids'] as List<dynamic>?)
              ?.map((e) => e as String)
              .toList() ??
          [],
      actionOptions: (json['action_options'] as List<dynamic>?)
              ?.map((e) => e as String)
              .toList() ??
          [],
      actionData: (json['action_data'] as Map<String, dynamic>?) ?? {},
      priority: json['priority'] as int? ?? 0,
      urgency: _parseUrgency(json['urgency'] as String?),
      expiresAt: json['expires_at'] != null
          ? TimezoneUtils.parseApiTime(json['expires_at'] as String)
          : null,
      createdAt: TimezoneUtils.parseApiTime(json['created_at'] as String),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'type': _typeToString(type),
      'title': title,
      'content': content,
      'icon': icon,
      'related_event_ids': relatedEventIds,
      'related_member_ids': relatedMemberIds,
      'related_travel_ids': relatedTravelIds,
      'action_options': actionOptions,
      'action_data': actionData,
      'priority': priority,
      'urgency': _urgencyToString(urgency),
      'expires_at': expiresAt != null ? TimezoneUtils.toApiTime(expiresAt!) : null,
      'created_at': TimezoneUtils.toApiTime(createdAt),
    };
  }

  static SuggestionType _parseType(String type) {
    switch (type) {
      case 'location_correlation':
        return SuggestionType.locationCorrelation;
      case 'time_correlation':
        return SuggestionType.timeCorrelation;
      case 'person_correlation':
        return SuggestionType.personCorrelation;
      case 'history_correlation':
        return SuggestionType.historyCorrelation;
      case 'preparation_reminder':
        return SuggestionType.preparationReminder;
      case 'anniversary_reminder':
        return SuggestionType.anniversaryReminder;
      case 'gift_reminder':
        return SuggestionType.giftReminder;
      case 'meetup_suggestion':
        return SuggestionType.meetupSuggestion;
      default:
        return SuggestionType.timeCorrelation;
    }
  }

  static String _typeToString(SuggestionType type) {
    switch (type) {
      case SuggestionType.locationCorrelation:
        return 'location_correlation';
      case SuggestionType.timeCorrelation:
        return 'time_correlation';
      case SuggestionType.personCorrelation:
        return 'person_correlation';
      case SuggestionType.historyCorrelation:
        return 'history_correlation';
      case SuggestionType.preparationReminder:
        return 'preparation_reminder';
      case SuggestionType.anniversaryReminder:
        return 'anniversary_reminder';
      case SuggestionType.giftReminder:
        return 'gift_reminder';
      case SuggestionType.meetupSuggestion:
        return 'meetup_suggestion';
    }
  }

  static SuggestionUrgency _parseUrgency(String? urgency) {
    switch (urgency) {
      case 'high':
        return SuggestionUrgency.high;
      case 'low':
        return SuggestionUrgency.low;
      default:
        return SuggestionUrgency.normal;
    }
  }

  static String _urgencyToString(SuggestionUrgency urgency) {
    switch (urgency) {
      case SuggestionUrgency.high:
        return 'high';
      case SuggestionUrgency.low:
        return 'low';
      case SuggestionUrgency.normal:
        return 'normal';
    }
  }
}

/// Response model for suggestion list
class SuggestionListResponse {
  final List<SmartSuggestionModel> suggestions;
  final int total;
  final DateTime generatedAt;

  const SuggestionListResponse({
    required this.suggestions,
    required this.total,
    required this.generatedAt,
  });

  factory SuggestionListResponse.fromJson(Map<String, dynamic> json) {
    return SuggestionListResponse(
      suggestions: (json['suggestions'] as List<dynamic>)
          .map((e) => SmartSuggestionModel.fromJson(e as Map<String, dynamic>))
          .toList(),
      total: json['total'] as int,
      generatedAt: TimezoneUtils.parseApiTime(json['generated_at'] as String),
    );
  }
}

/// Request model for executing suggestion action
class SuggestionActionRequest {
  final String suggestionId;
  final String action;
  final Map<String, dynamic>? params;

  const SuggestionActionRequest({
    required this.suggestionId,
    required this.action,
    this.params,
  });

  Map<String, dynamic> toJson() {
    return {
      'suggestion_id': suggestionId,
      'action': action,
      if (params != null) 'params': params,
    };
  }
}

/// Response model for suggestion action
class SuggestionActionResponse {
  final bool success;
  final String action;
  final String message;
  final String? nextStep;
  final Map<String, dynamic>? data;

  const SuggestionActionResponse({
    required this.success,
    required this.action,
    required this.message,
    this.nextStep,
    this.data,
  });

  factory SuggestionActionResponse.fromJson(Map<String, dynamic> json) {
    return SuggestionActionResponse(
      success: json['success'] as bool,
      action: json['action'] as String,
      message: json['message'] as String,
      nextStep: json['next_step'] as String?,
      data: json['data'] as Map<String, dynamic>?,
    );
  }
}
