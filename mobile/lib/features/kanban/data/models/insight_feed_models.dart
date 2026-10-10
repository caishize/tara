import '../../../../core/utils/timezone_utils.dart';
import 'kanban_models.dart';

/// Parsed ActionSpec from the backend.
///
/// Backend sends `{label, action_type, action_payload}` dicts.
/// This model extracts the canonical `actionType` (used for routing/dispatch)
/// and the human-readable `label` (used for chip display text).
class ActionOptionModel {
  final String actionType;
  final String label;
  final Map<String, dynamic> payload;

  const ActionOptionModel({
    required this.actionType,
    required this.label,
    this.payload = const {},
  });

  /// Parse from JSON dict or plain string (backward compat).
  factory ActionOptionModel.fromDynamic(dynamic raw) {
    if (raw is Map<String, dynamic>) {
      return ActionOptionModel(
        actionType: raw['action_type'] as String? ?? '',
        label: raw['label'] as String? ?? '',
        payload: raw['action_payload'] as Map<String, dynamic>? ?? const {},
      );
    }
    // Legacy plain string: use as both actionType and label
    final s = raw.toString();
    return ActionOptionModel(actionType: s, label: s);
  }

  static List<ActionOptionModel> parseList(dynamic json) {
    if (json is! List) return const [];
    return json.map(ActionOptionModel.fromDynamic).toList();
  }
}

/// A related event referenced by an insight feed item
class InsightRelatedEventModel {
  final String id;
  final String title;
  final String? eventType;
  final DateTime? startTime;
  final String? location;
  final String status;

  const InsightRelatedEventModel({
    required this.id,
    required this.title,
    this.eventType,
    this.startTime,
    this.location,
    this.status = 'active',
  });

  factory InsightRelatedEventModel.fromJson(Map<String, dynamic> json) {
    return InsightRelatedEventModel(
      id: json['id'] as String? ?? '',
      title: json['title'] as String? ?? '',
      eventType: json['event_type'] as String?,
      startTime: json['start_time'] != null
          ? TimezoneUtils.parseApiTime(json['start_time'] as String)
          : null,
      location: json['location'] as String?,
      status: json['status'] as String? ?? 'active',
    );
  }

  InsightRelatedEventModel copyWith({
    String? id,
    String? title,
    String? eventType,
    DateTime? startTime,
    String? location,
    String? status,
  }) {
    return InsightRelatedEventModel(
      id: id ?? this.id,
      title: title ?? this.title,
      eventType: eventType ?? this.eventType,
      startTime: startTime ?? this.startTime,
      location: location ?? this.location,
      status: status ?? this.status,
    );
  }
}

/// A related family member referenced by an insight feed item
class InsightRelatedMemberModel {
  final String id;
  final String name;
  final String? relationship;
  final String? avatarUrl;

  const InsightRelatedMemberModel({
    required this.id,
    required this.name,
    this.relationship,
    this.avatarUrl,
  });

  factory InsightRelatedMemberModel.fromJson(Map<String, dynamic> json) {
    return InsightRelatedMemberModel(
      id: json['id'] as String? ?? '',
      name: json['name'] as String? ?? '',
      relationship: json['relationship'] as String?,
      avatarUrl: json['avatar_url'] as String?,
    );
  }

  InsightRelatedMemberModel copyWith({
    String? id,
    String? name,
    String? relationship,
    String? avatarUrl,
  }) {
    return InsightRelatedMemberModel(
      id: id ?? this.id,
      name: name ?? this.name,
      relationship: relationship ?? this.relationship,
      avatarUrl: avatarUrl ?? this.avatarUrl,
    );
  }
}

/// A related trip referenced by an insight feed item
class InsightRelatedTripModel {
  final String id;
  final String name;
  final DateTime? startDate;
  final DateTime? endDate;
  final String? status;

  const InsightRelatedTripModel({
    required this.id,
    required this.name,
    this.startDate,
    this.endDate,
    this.status,
  });

  factory InsightRelatedTripModel.fromJson(Map<String, dynamic> json) {
    return InsightRelatedTripModel(
      id: json['id'] as String? ?? '',
      name: json['name'] as String? ?? '',
      startDate: json['start_date'] != null
          ? DateTime.tryParse(json['start_date'] as String)
          : null,
      endDate: json['end_date'] != null
          ? DateTime.tryParse(json['end_date'] as String)
          : null,
      status: json['status'] as String?,
    );
  }

  InsightRelatedTripModel copyWith({
    String? id,
    String? name,
    DateTime? startDate,
    DateTime? endDate,
    String? status,
  }) {
    return InsightRelatedTripModel(
      id: id ?? this.id,
      name: name ?? this.name,
      startDate: startDate ?? this.startDate,
      endDate: endDate ?? this.endDate,
      status: status ?? this.status,
    );
  }
}

/// A single insight item in the insight-centric feed
class InsightFeedItemModel {
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
  final String? sourceContext;
  final List<InsightRelatedEventModel> relatedEvents;
  final List<InsightRelatedMemberModel> relatedMembers;
  final InsightRelatedTripModel? relatedTrip;

  const InsightFeedItemModel({
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
    this.sourceContext,
    this.relatedEvents = const [],
    this.relatedMembers = const [],
    this.relatedTrip,
  });

  factory InsightFeedItemModel.fromJson(Map<String, dynamic> json) {
    return InsightFeedItemModel(
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
      sourceContext: json['source_context'] as String?,
      relatedEvents: List<InsightRelatedEventModel>.from(
        (json['related_events'] as List<dynamic>?)?.map(
              (e) => InsightRelatedEventModel.fromJson(
                  e as Map<String, dynamic>),
            ) ??
            const [],
      ),
      relatedMembers: List<InsightRelatedMemberModel>.from(
        (json['related_members'] as List<dynamic>?)?.map(
              (e) => InsightRelatedMemberModel.fromJson(
                  e as Map<String, dynamic>),
            ) ??
            const [],
      ),
      relatedTrip: json['related_trip'] != null
          ? InsightRelatedTripModel.fromJson(
              json['related_trip'] as Map<String, dynamic>)
          : null,
    );
  }

  /// Computes a continuous visual weight in [0.2, 0.95] from urgency and priority.
  ///
  /// Named [_urgencyVisualWeight] conceptually to distinguish this client-side
  /// computation from a future server-sent `visual_weight` field.
  /// When the backend adds `visual_weight`, this getter should check that field
  /// first and fall back to the formula.
  double get visualWeight {
    final base = switch (urgency) {
      'urgent' => 0.75,
      'important' => 0.55,
      _ => 0.35,
    };
    // priority 1=highest, 10=lowest. Each rank adds/subtracts ±0.015.
    final priorityOffset = (5 - priority.clamp(1, 10)) * 0.015;
    return (base + priorityOffset).clamp(0.2, 0.95);
  }

  InsightFeedItemModel copyWith({
    String? id,
    String? title,
    String? content,
    String? insightType,
    int? priority,
    String? urgency,
    DateTime? createdAt,
    String? actionType,
    Map<String, dynamic>? actionData,
    List<ActionOptionModel>? actionOptions,
    String? contextHint,
    String? sourceContext,
    List<InsightRelatedEventModel>? relatedEvents,
    List<InsightRelatedMemberModel>? relatedMembers,
    InsightRelatedTripModel? relatedTrip,
  }) {
    return InsightFeedItemModel(
      id: id ?? this.id,
      title: title ?? this.title,
      content: content ?? this.content,
      insightType: insightType ?? this.insightType,
      priority: priority ?? this.priority,
      urgency: urgency ?? this.urgency,
      createdAt: createdAt ?? this.createdAt,
      actionType: actionType ?? this.actionType,
      actionData: actionData ?? this.actionData,
      actionOptions: actionOptions ?? this.actionOptions,
      contextHint: contextHint ?? this.contextHint,
      sourceContext: sourceContext ?? this.sourceContext,
      relatedEvents: relatedEvents ?? this.relatedEvents,
      relatedMembers: relatedMembers ?? this.relatedMembers,
      relatedTrip: relatedTrip ?? this.relatedTrip,
    );
  }
}

/// A semantically grouped cluster of insights.
///
/// PLAN-004: Added server-driven display hints ([expandedByDefault],
/// [icon], [accentColor]) so the client can defer group presentation
/// decisions to the server.
class InsightGroupModel {
  final String groupId;
  final String title;
  final String? subtitle;
  final List<InsightFeedItemModel> insights;
  final List<KanbanEventModel> preparationEvents;
  final List<KanbanEventModel> standaloneEvents;

  /// Whether this group should be expanded by default on first load.
  /// Defaults to `true` for backward compatibility.
  final bool expandedByDefault;

  /// Optional server-provided icon identifier (e.g. 'flash_on').
  /// When null, the client falls back to its hardcoded icon map.
  final String? icon;

  /// Optional server-provided hex accent color (e.g. '#2D7A46').
  /// When null, the client falls back to its hardcoded color map.
  final String? accentColor;

  const InsightGroupModel({
    required this.groupId,
    required this.title,
    this.subtitle,
    this.insights = const [],
    this.preparationEvents = const [],
    this.standaloneEvents = const [],
    this.expandedByDefault = true,
    this.icon,
    this.accentColor,
  });

  factory InsightGroupModel.fromJson(Map<String, dynamic> json) {
    return InsightGroupModel(
      groupId: json['group_id'] as String? ?? '',
      title: json['title'] as String? ?? '',
      subtitle: json['subtitle'] as String?,
      insights: List<InsightFeedItemModel>.from(
        (json['insights'] as List<dynamic>?)?.map(
              (e) =>
                  InsightFeedItemModel.fromJson(e as Map<String, dynamic>),
            ) ??
            const [],
      ),
      preparationEvents: _parseEventList(json['preparation_events']),
      standaloneEvents: _parseEventList(json['standalone_events']),
      expandedByDefault: json['expanded_by_default'] as bool? ?? true,
      icon: json['icon'] as String?,
      accentColor: json['accent_color'] as String?,
    );
  }

  static List<KanbanEventModel> _parseEventList(dynamic json) {
    if (json == null) return const [];
    return List<KanbanEventModel>.from(
      (json as List<dynamic>).map(
        (e) => KanbanEventModel.fromJson(e as Map<String, dynamic>),
      ),
    );
  }

  bool get isEmpty =>
      insights.isEmpty &&
      preparationEvents.isEmpty &&
      standaloneEvents.isEmpty;

  /// PLAN-002: Additive copyWith — preserves constructor signature.
  ///
  /// All parameters are optional; omitted parameters retain the current value.
  InsightGroupModel copyWith({
    String? groupId,
    String? title,
    String? subtitle,
    List<InsightFeedItemModel>? insights,
    List<KanbanEventModel>? preparationEvents,
    List<KanbanEventModel>? standaloneEvents,
    bool? expandedByDefault,
    String? icon,
    String? accentColor,
  }) {
    return InsightGroupModel(
      groupId: groupId ?? this.groupId,
      title: title ?? this.title,
      subtitle: subtitle ?? this.subtitle,
      insights: insights ?? this.insights,
      preparationEvents: preparationEvents ?? this.preparationEvents,
      standaloneEvents: standaloneEvents ?? this.standaloneEvents,
      expandedByDefault: expandedByDefault ?? this.expandedByDefault,
      icon: icon ?? this.icon,
      accentColor: accentColor ?? this.accentColor,
    );
  }
}

/// Top-level insight feed API response.
///
/// Supports both grouped (`?format=grouped`) and flat (legacy) formats.
/// When [groups] is non-empty, the UI renders group sections.
/// When [groups] is empty, the UI falls back to the flat [insights] list.
class InsightFeedResponseModel {
  final List<InsightGroupModel> groups;
  final List<InsightFeedItemModel> insights;
  final List<KanbanEventModel> standaloneEvents;
  final List<KanbanEventModel> laterEvents;
  final List<KanbanEventModel> needsPreparation;

  /// Opaque cursor for fetching the next page. Null when no more pages.
  final String? nextCursor;

  /// Whether the backend has more items beyond this page.
  final bool hasMore;

  const InsightFeedResponseModel({
    this.groups = const [],
    this.insights = const [],
    this.standaloneEvents = const [],
    this.laterEvents = const [],
    this.needsPreparation = const [],
    this.nextCursor,
    this.hasMore = false,
  });

  factory InsightFeedResponseModel.fromJson(Map<String, dynamic> json) {
    return InsightFeedResponseModel(
      groups: List<InsightGroupModel>.from(
        (json['groups'] as List<dynamic>?)?.map(
              (e) =>
                  InsightGroupModel.fromJson(e as Map<String, dynamic>),
            ) ??
            const [],
      ),
      insights: List<InsightFeedItemModel>.from(
        (json['insights'] as List<dynamic>?)?.map(
              (e) => InsightFeedItemModel.fromJson(e as Map<String, dynamic>),
            ) ??
            const [],
      ),
      standaloneEvents: _parseEventList(json['standalone_events']),
      laterEvents: _parseEventList(json['later_events']),
      needsPreparation: _parseEventList(json['needs_preparation']),
      nextCursor: json['next_cursor'] as String?,
      hasMore: json['has_more'] as bool? ?? false,
    );
  }

  static List<KanbanEventModel> _parseEventList(dynamic json) {
    if (json == null) return const [];
    return List<KanbanEventModel>.from(
      (json as List<dynamic>).map(
        (e) => KanbanEventModel.fromJson(e as Map<String, dynamic>),
      ),
    );
  }

  /// PLAN-009: [laterEvents], [standaloneEvents], and [needsPreparation]
  /// use nullable-wrapper callbacks so callers can distinguish
  /// "leave unchanged" (omit) from "set to empty list" (pass `() => []`).
  /// This prevents page-1 data from being silently dropped during
  /// pagination merge when page-2 omits those fields.
  InsightFeedResponseModel copyWith({
    List<InsightGroupModel>? groups,
    List<InsightFeedItemModel>? insights,
    List<KanbanEventModel>? Function()? standaloneEvents,
    List<KanbanEventModel>? Function()? laterEvents,
    List<KanbanEventModel>? Function()? needsPreparation,
    String? Function()? nextCursor,
    bool? hasMore,
  }) {
    return InsightFeedResponseModel(
      groups: groups ?? this.groups,
      insights: insights ?? this.insights,
      standaloneEvents: standaloneEvents != null
          ? (standaloneEvents() ?? this.standaloneEvents)
          : this.standaloneEvents,
      laterEvents: laterEvents != null
          ? (laterEvents() ?? this.laterEvents)
          : this.laterEvents,
      needsPreparation: needsPreparation != null
          ? (needsPreparation() ?? this.needsPreparation)
          : this.needsPreparation,
      nextCursor: nextCursor != null ? nextCursor() : this.nextCursor,
      hasMore: hasMore ?? this.hasMore,
    );
  }

  /// Whether the response uses the grouped format.
  bool get isGrouped => groups.isNotEmpty;

  bool get isEmpty =>
      groups.isEmpty &&
      insights.isEmpty &&
      standaloneEvents.isEmpty &&
      laterEvents.isEmpty &&
      needsPreparation.isEmpty;
}

/// A detail item for PendingAction display.
class ActionDetailItemModel {
  final String label;
  final String value;

  const ActionDetailItemModel({required this.label, required this.value});

  factory ActionDetailItemModel.fromJson(Map<String, dynamic> json) {
    return ActionDetailItemModel(
      label: json['label'] as String? ?? '',
      value: json['value'] as String? ?? '',
    );
  }
}

/// Response model for a PendingAction created from an insight.
class PendingActionResponseModel {
  final String id;
  final String actionType;
  final String status;
  final String displayTitle;
  final String description;
  final List<ActionDetailItemModel> displayDetails;
  final String? expiresAt;
  final String? createdAt;
  final bool canConfirm;
  final bool isExpired;

  const PendingActionResponseModel({
    required this.id,
    required this.actionType,
    required this.status,
    this.displayTitle = '',
    this.description = '',
    this.displayDetails = const [],
    this.expiresAt,
    this.createdAt,
    this.canConfirm = false,
    this.isExpired = false,
  });

  factory PendingActionResponseModel.fromJson(Map<String, dynamic> json) {
    return PendingActionResponseModel(
      id: json['id'] as String? ?? '',
      actionType: json['action_type'] as String? ?? '',
      status: json['status'] as String? ?? 'pending',
      displayTitle: json['display_title'] as String? ?? '',
      description: json['description'] as String? ?? '',
      displayDetails: (json['display_details'] as List<dynamic>?)
              ?.map((d) =>
                  ActionDetailItemModel.fromJson(d as Map<String, dynamic>))
              .toList() ??
          const [],
      expiresAt: json['expires_at'] as String?,
      createdAt: json['created_at'] as String?,
      canConfirm: json['can_confirm'] as bool? ?? false,
      isExpired: json['is_expired'] as bool? ?? false,
    );
  }
}
