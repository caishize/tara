/// Data models for the trip context endpoint response.
library;

class ParticipantInfoModel {
  final String id;
  final String name;
  final String? nickname;
  final String? relation;
  final int? age;
  final bool isChild;
  final String? contextLabel;
  final List<String> actionTags;

  const ParticipantInfoModel({
    required this.id,
    required this.name,
    this.nickname,
    this.relation,
    this.age,
    this.isChild = false,
    this.contextLabel,
    this.actionTags = const [],
  });

  factory ParticipantInfoModel.fromJson(Map<String, dynamic> json) {
    return ParticipantInfoModel(
      id: json['id'] as String? ?? '',
      name: json['name'] as String? ?? '',
      nickname: json['nickname'] as String?,
      relation: json['relation'] as String?,
      age: (json['age'] as num?)?.toInt(),
      isChild: json['is_child'] as bool? ?? false,
      contextLabel: json['context_label'] as String?,
      actionTags: (json['action_tags'] as List<dynamic>?)
              ?.map((e) => e as String)
              .toList() ??
          const [],
    );
  }

  String get displayName => nickname ?? name;
}

class WeatherAlertModel {
  final String destination;
  final String condition;
  final int temperature;
  final int? highTemp;
  final int? lowTemp;
  final String? alertMessage;
  final String? advice;

  const WeatherAlertModel({
    required this.destination,
    required this.condition,
    required this.temperature,
    this.highTemp,
    this.lowTemp,
    this.alertMessage,
    this.advice,
  });

  factory WeatherAlertModel.fromJson(Map<String, dynamic> json) {
    return WeatherAlertModel(
      destination: json['destination'] as String? ?? '',
      condition: json['condition'] as String? ?? '',
      temperature: (json['temperature'] as num?)?.toInt() ?? 0,
      highTemp: (json['high_temp'] as num?)?.toInt(),
      lowTemp: (json['low_temp'] as num?)?.toInt(),
      alertMessage: json['alert_message'] as String?,
      advice: json['advice'] as String?,
    );
  }

  bool get hasAlert => alertMessage != null && alertMessage!.isNotEmpty;
}

class TripPrepItemModel {
  final String key;
  final String text;
  final bool done;
  final String source;
  final String? actionLabel;

  const TripPrepItemModel({
    required this.key,
    required this.text,
    this.done = false,
    this.source = 'manual',
    this.actionLabel,
  });

  factory TripPrepItemModel.fromJson(Map<String, dynamic> json) {
    final done = json['done'] as bool? ?? false;
    return TripPrepItemModel(
      key: json['key'] as String? ?? '',
      // Trip detail context uses `text`; kanban preparation update API uses `item`.
      text: (json['text'] as String?) ?? (json['item'] as String?) ?? '',
      done: done,
      source: json['source'] as String? ?? 'manual',
      // Keep action affordance when backend omits `action_label` in patch response.
      actionLabel: (json['action_label'] as String?) ?? (!done ? '去看看' : null),
    );
  }
}

/// A "thing you can do along the way" from the event graph.
class SideActivityModel {
  final String id;
  final String title;
  final String? reason;
  final String priority;
  final String targetType;
  final String? icon;

  const SideActivityModel({
    required this.id,
    required this.title,
    this.reason,
    this.priority = 'medium',
    this.targetType = 'task',
    this.icon,
  });

  factory SideActivityModel.fromJson(Map<String, dynamic> json) {
    return SideActivityModel(
      id: json['id'] as String? ?? '',
      title: json['title'] as String? ?? '',
      reason: json['reason'] as String?,
      priority: json['priority'] as String? ?? 'medium',
      targetType: json['target_type'] as String? ?? 'task',
      icon: json['icon'] as String?,
    );
  }
}

/// A structured highlight from the trip's recommendation context.
class RecommendationHighlightModel {
  final String icon;
  final String label;
  final String detail;
  final String category;

  const RecommendationHighlightModel({
    required this.icon,
    required this.label,
    this.detail = '',
    this.category = 'general',
  });

  factory RecommendationHighlightModel.fromJson(Map<String, dynamic> json) {
    return RecommendationHighlightModel(
      icon: json['icon'] as String? ?? 'lightbulb',
      label: json['label'] as String? ?? '',
      detail: json['detail'] as String? ?? '',
      category: json['category'] as String? ?? 'general',
    );
  }
}

class TripContextModel {
  final String tripId;
  final List<ParticipantInfoModel> participants;
  final WeatherAlertModel? weather;
  final List<TripPrepItemModel> preparationItems;
  final String? curatedEventId;
  final String? insightText;
  final List<SideActivityModel> sideActivities;
  final List<RecommendationHighlightModel> recommendationHighlights;

  const TripContextModel({
    required this.tripId,
    this.participants = const [],
    this.weather,
    this.preparationItems = const [],
    this.curatedEventId,
    this.insightText,
    this.sideActivities = const [],
    this.recommendationHighlights = const [],
  });

  factory TripContextModel.fromJson(Map<String, dynamic> json) {
    return TripContextModel(
      tripId: json['trip_id'] as String? ?? '',
      participants: (json['participants'] as List<dynamic>?)
              ?.map((e) =>
                  ParticipantInfoModel.fromJson(e as Map<String, dynamic>))
              .toList() ??
          const [],
      weather: json['weather'] != null
          ? WeatherAlertModel.fromJson(json['weather'] as Map<String, dynamic>)
          : null,
      preparationItems: (json['preparation_items'] as List<dynamic>?)
              ?.map(
                  (e) => TripPrepItemModel.fromJson(e as Map<String, dynamic>))
              .toList() ??
          const [],
      curatedEventId: json['curated_event_id'] as String?,
      insightText: json['insight_text'] as String?,
      sideActivities: (json['side_activities'] as List<dynamic>?)
              ?.map(
                  (e) => SideActivityModel.fromJson(e as Map<String, dynamic>))
              .toList() ??
          const [],
      recommendationHighlights:
          (json['recommendation_highlights'] as List<dynamic>?)
                  ?.map((e) => RecommendationHighlightModel.fromJson(
                      e as Map<String, dynamic>))
                  .toList() ??
              const [],
    );
  }
}
