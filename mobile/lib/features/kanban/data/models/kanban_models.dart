import '../../../../core/utils/timezone_utils.dart';
import '../../domain/entities/curated_event.dart';
import 'insight_feed_models.dart';

/// Preparation item within a kanban event
class PreparationItemModel {
  final String? key;
  final String item;
  final String source;
  final bool done;

  const PreparationItemModel({
    this.key,
    required this.item,
    this.source = 'manual',
    this.done = false,
  });

  factory PreparationItemModel.fromJson(Map<String, dynamic> json) {
    return PreparationItemModel(
      key: json['key'] as String?,
      item: json['item'] as String? ?? '',
      source: json['source'] as String? ?? 'manual',
      done: json['done'] as bool? ?? false,
    );
  }

  PreparationItemModel copyWith({bool? done}) {
    return PreparationItemModel(
      key: key,
      item: item,
      source: source,
      done: done ?? this.done,
    );
  }
}

/// A single event in the kanban view
class KanbanEventModel {
  final String id;
  final String title;
  final CuratedEventType? eventType;
  final DateTime? startTime;
  final DateTime? endTime;
  final String? location;
  final String status;
  final String priority;
  final String? notes;
  final String? tripId;
  final String? tripName;
  final List<PreparationItemModel> preparationItems;
  final List<String>? tags;
  final String visibilityTier;

  const KanbanEventModel({
    required this.id,
    required this.title,
    this.eventType,
    this.startTime,
    this.endTime,
    this.location,
    this.status = 'pending',
    this.priority = 'normal',
    this.notes,
    this.tripId,
    this.tripName,
    this.preparationItems = const [],
    this.tags,
    this.visibilityTier = 'standard',
  });

  /// Whether this event should be visually emphasized
  bool get isFocusEvent => visibilityTier == 'focus';

  factory KanbanEventModel.fromJson(Map<String, dynamic> json) {
    return KanbanEventModel(
      id: json['id'] as String? ?? '',
      title: json['title'] as String? ?? '',
      eventType: CuratedEventType.fromString(json['event_type'] as String?),
      startTime: json['start_time'] != null
          ? TimezoneUtils.parseApiTime(json['start_time'] as String)
          : null,
      endTime: json['end_time'] != null
          ? TimezoneUtils.parseApiTime(json['end_time'] as String)
          : null,
      location: json['location'] as String?,
      status: json['status'] as String? ?? 'pending',
      priority: json['priority'] as String? ?? 'normal',
      notes: json['notes'] as String?,
      tripId: json['trip_id'] as String?,
      tripName: json['trip_name'] as String?,
      preparationItems: (json['preparation_items'] as List<dynamic>?)
              ?.map((e) =>
                  PreparationItemModel.fromJson(e as Map<String, dynamic>))
              .toList() ??
          const [],
      tags: (json['tags'] as List<dynamic>?)
          ?.map((e) => e.toString())
          .toList(),
      visibilityTier: json['visibility_tier'] as String? ?? 'standard',
    );
  }

  KanbanEventModel copyWith({
    String? id,
    String? title,
    CuratedEventType? eventType,
    DateTime? startTime,
    DateTime? endTime,
    String? location,
    String? status,
    String? priority,
    String? notes,
    String? tripId,
    String? tripName,
    List<PreparationItemModel>? preparationItems,
    List<String>? tags,
    String? visibilityTier,
  }) {
    return KanbanEventModel(
      id: id ?? this.id,
      title: title ?? this.title,
      eventType: eventType ?? this.eventType,
      startTime: startTime ?? this.startTime,
      endTime: endTime ?? this.endTime,
      location: location ?? this.location,
      status: status ?? this.status,
      priority: priority ?? this.priority,
      notes: notes ?? this.notes,
      tripId: tripId ?? this.tripId,
      tripName: tripName ?? this.tripName,
      preparationItems: preparationItems ?? this.preparationItems,
      tags: tags ?? this.tags,
      visibilityTier: visibilityTier ?? this.visibilityTier,
    );
  }

  int get prepDoneCount => preparationItems.where((i) => i.done).length;

  int get prepTotalCount => preparationItems.length;

  bool get allPrepDone =>
      preparationItems.isNotEmpty && prepDoneCount == prepTotalCount;

  bool get hasPendingPrep =>
      preparationItems.isNotEmpty && prepDoneCount < prepTotalCount;
}

/// Insight surfaced in the kanban view
class KanbanInsightModel {
  final String id;
  final String title;
  final String content;
  final String insightType;
  final int priority;
  final String urgency;
  final DateTime? createdAt;
  final String? actionType;
  final Map<String, dynamic>? actionData;
  final List<ActionOptionModel> actionOptions;
  final String? contextHint;

  const KanbanInsightModel({
    required this.id,
    required this.title,
    required this.content,
    required this.insightType,
    this.priority = 5,
    this.urgency = 'normal',
    this.createdAt,
    this.actionType,
    this.actionData,
    this.actionOptions = const [],
    this.contextHint,
  });

  factory KanbanInsightModel.fromJson(Map<String, dynamic> json) {
    return KanbanInsightModel(
      id: json['id'] as String? ?? '',
      title: json['title'] as String? ?? '',
      content: json['content'] as String? ?? '',
      insightType: json['insight_type'] as String? ?? '',
      priority: json['priority'] as int? ?? 5,
      urgency: json['urgency'] as String? ?? 'normal',
      createdAt: json['created_at'] != null
          ? TimezoneUtils.parseApiTime(json['created_at'] as String)
          : null,
      actionType: json['action_type'] as String?,
      actionData: json['action_data'] as Map<String, dynamic>?,
      actionOptions: ActionOptionModel.parseList(json['action_options']),
      contextHint: json['context_hint'] as String?,
    );
  }
}

/// Top-level kanban API response
class KanbanResponseModel {
  final List<KanbanEventModel> thisWeek;
  final List<KanbanEventModel> needsPreparation;
  final List<KanbanEventModel> monthly;
  final List<KanbanEventModel> later;
  final List<KanbanInsightModel> insights;

  const KanbanResponseModel({
    this.thisWeek = const [],
    this.needsPreparation = const [],
    this.monthly = const [],
    this.later = const [],
    this.insights = const [],
  });

  factory KanbanResponseModel.fromJson(Map<String, dynamic> json) {
    return KanbanResponseModel(
      thisWeek: _parseEventList(json['this_week']),
      needsPreparation: _parseEventList(json['needs_preparation']),
      monthly: _parseEventList(json['monthly']),
      later: _parseEventList(json['later']),
      insights: (json['insights'] as List<dynamic>?)
              ?.map((e) =>
                  KanbanInsightModel.fromJson(e as Map<String, dynamic>))
              .toList() ??
          const [],
    );
  }

  static List<KanbanEventModel> _parseEventList(dynamic json) {
    if (json == null) return const [];
    return (json as List<dynamic>)
        .map((e) => KanbanEventModel.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  KanbanResponseModel copyWith({
    List<KanbanEventModel>? thisWeek,
    List<KanbanEventModel>? needsPreparation,
    List<KanbanEventModel>? monthly,
    List<KanbanEventModel>? later,
    List<KanbanInsightModel>? insights,
  }) {
    return KanbanResponseModel(
      thisWeek: thisWeek ?? this.thisWeek,
      needsPreparation: needsPreparation ?? this.needsPreparation,
      monthly: monthly ?? this.monthly,
      later: later ?? this.later,
      insights: insights ?? this.insights,
    );
  }

  bool get isEmpty =>
      thisWeek.isEmpty &&
      needsPreparation.isEmpty &&
      monthly.isEmpty &&
      later.isEmpty &&
      insights.isEmpty;
}
