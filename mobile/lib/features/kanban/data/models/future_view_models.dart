import 'dart:ui';

import 'insight_feed_models.dart';

class FutureViewUpcomingPageModel {
  final List<FutureViewUpcomingModel> items;
  final bool hasMore;
  final int total;

  const FutureViewUpcomingPageModel({
    required this.items,
    this.hasMore = false,
    this.total = 0,
  });

  factory FutureViewUpcomingPageModel.fromJson(Map<String, dynamic> json) {
    return FutureViewUpcomingPageModel(
      items: (json['items'] as List<dynamic>?)
              ?.map((e) =>
                  FutureViewUpcomingModel.fromJson(e as Map<String, dynamic>))
              .toList() ??
          const [],
      hasMore: json['has_more'] as bool? ?? false,
      total: json['total'] as int? ?? 0,
    );
  }
}

/// Parse a hex color string (e.g. "#3D8A5A" or "3D8A5A") into a [Color].
Color _parseHex(String hex) {
  final cleaned = hex.replaceFirst('#', '');
  final value = int.tryParse(cleaned, radix: 16);
  if (value == null) return const Color(0xFF9C9B99);
  if (cleaned.length == 6) return Color(0xFF000000 | value);
  return Color(value);
}

class FutureViewTripTaskModel {
  final String id;
  final String title;
  final String subtitle;
  final bool done;
  final String actionLabel;
  final String actionType;
  final bool isPrimaryAction;
  final String? memberColor;

  const FutureViewTripTaskModel({
    required this.id,
    required this.title,
    required this.subtitle,
    required this.done,
    required this.actionLabel,
    required this.actionType,
    required this.isPrimaryAction,
    this.memberColor,
  });

  Color? get memberColorValue =>
      memberColor != null ? _parseHex(memberColor!) : null;

  factory FutureViewTripTaskModel.fromJson(Map<String, dynamic> json) {
    return FutureViewTripTaskModel(
      id: json['id'] as String,
      title: json['title'] as String,
      subtitle: json['subtitle'] as String? ?? '',
      done: json['done'] as bool? ?? false,
      actionLabel: json['action_label'] as String? ?? '',
      actionType: json['action_type'] as String? ?? '',
      isPrimaryAction: json['is_primary_action'] as bool? ?? false,
      memberColor: json['member_color'] as String?,
    );
  }
}

class FutureViewTripParticipant {
  final String id;
  final String name;
  final String color;

  const FutureViewTripParticipant({
    required this.id,
    required this.name,
    required this.color,
  });

  Color get colorValue => _parseHex(color);

  factory FutureViewTripParticipant.fromJson(Map<String, dynamic> json) {
    return FutureViewTripParticipant(
      id: json['id'] as String,
      name: json['name'] as String,
      color: json['color'] as String? ?? '#9C9B99',
    );
  }
}

class FutureViewTripModel {
  final String id;
  final String name;
  final String emoji;
  final String category;
  final DateTime startDate;
  final DateTime endDate;
  final int daysUntil;
  final int doneCount;
  final int totalCount;
  final List<FutureViewTripParticipant> participants;
  final List<FutureViewTripTaskModel> tasks;
  final List<InsightFeedItemModel> insights;

  const FutureViewTripModel({
    required this.id,
    required this.name,
    required this.emoji,
    required this.category,
    required this.startDate,
    required this.endDate,
    required this.daysUntil,
    required this.doneCount,
    required this.totalCount,
    required this.participants,
    required this.tasks,
    this.insights = const [],
  });

  bool get isBusiness => category == 'business';

  FutureViewTripModel copyWith({
    List<FutureViewTripTaskModel>? tasks,
    int? doneCount,
    List<InsightFeedItemModel>? insights,
  }) {
    return FutureViewTripModel(
      id: id,
      name: name,
      emoji: emoji,
      category: category,
      startDate: startDate,
      endDate: endDate,
      daysUntil: daysUntil,
      doneCount: doneCount ?? this.doneCount,
      totalCount: totalCount,
      participants: participants,
      tasks: tasks ?? this.tasks,
      insights: insights ?? this.insights,
    );
  }

  factory FutureViewTripModel.fromJson(Map<String, dynamic> json) {
    return FutureViewTripModel(
      id: json['id'] as String,
      name: json['name'] as String,
      emoji: json['emoji'] as String? ?? '',
      category: json['category'] as String? ?? 'personal',
      startDate: DateTime.parse(json['start_date'] as String),
      endDate: DateTime.parse(json['end_date'] as String),
      daysUntil: json['days_until'] as int? ?? 0,
      doneCount: json['done_count'] as int? ?? 0,
      totalCount: json['total_count'] as int? ?? 0,
      participants: (json['participants'] as List<dynamic>?)
              ?.map((e) => FutureViewTripParticipant.fromJson(
                  e as Map<String, dynamic>))
              .toList() ??
          const [],
      tasks: (json['tasks'] as List<dynamic>?)
              ?.map((e) =>
                  FutureViewTripTaskModel.fromJson(e as Map<String, dynamic>))
              .toList() ??
          const [],
      insights: (json['insights'] as List<dynamic>?)
              ?.map((e) =>
                  InsightFeedItemModel.fromJson(e as Map<String, dynamic>))
              .toList() ??
          const [],
    );
  }
}

class FutureViewSuggestionSubItem {
  final String id;
  final String label;
  final String description;
  final String actionType;
  final bool isPendingAction;

  const FutureViewSuggestionSubItem({
    required this.id,
    required this.label,
    this.description = '',
    this.actionType = '',
    this.isPendingAction = false,
  });

  factory FutureViewSuggestionSubItem.fromJson(Map<String, dynamic> json) {
    return FutureViewSuggestionSubItem(
      id: json['id'] as String,
      label: json['label'] as String? ?? '',
      description: json['description'] as String? ?? '',
      actionType: json['action_type'] as String? ?? '',
      isPendingAction: json['is_pending_action'] as bool? ?? false,
    );
  }
}

class FutureViewSuggestionModel {
  final String id;
  final String insightId;
  final String title;
  final String description;
  final String tagEmoji;
  final String tagLabel;
  final String tagColor;
  final String actionLabel;
  final String actionType;
  final Map<String, dynamic>? actionData;
  final String? relatedTripId;
  final List<FutureViewSuggestionSubItem> subItems;
  final List<ActionOptionModel> actionOptions;
  final String groupKey;
  final String groupLabel;

  const FutureViewSuggestionModel({
    required this.id,
    required this.insightId,
    required this.title,
    required this.description,
    required this.tagEmoji,
    required this.tagLabel,
    required this.tagColor,
    required this.actionLabel,
    required this.actionType,
    this.actionData,
    this.relatedTripId,
    this.subItems = const [],
    this.actionOptions = const [],
    this.groupKey = '',
    this.groupLabel = '',
  });

  Color get tagColorValue => _parseHex(tagColor);

  bool get hasTripContext => relatedTripId != null && relatedTripId!.isNotEmpty;

  bool get hasSubItems => subItems.isNotEmpty;

  bool get hasActionOptions => actionOptions.isNotEmpty;

  factory FutureViewSuggestionModel.fromJson(Map<String, dynamic> json) {
    return FutureViewSuggestionModel(
      id: json['id'] as String,
      insightId: json['insight_id'] as String? ?? '',
      title: json['title'] as String,
      description: json['description'] as String? ?? '',
      tagEmoji: json['tag_emoji'] as String? ?? '',
      tagLabel: json['tag_label'] as String? ?? '',
      tagColor: json['tag_color'] as String? ?? '#3D8A5A',
      actionLabel: json['action_label'] as String? ?? '',
      actionType: json['action_type'] as String? ?? '',
      actionData: json['action_data'] as Map<String, dynamic>?,
      relatedTripId: json['related_trip_id'] as String?,
      subItems: (json['sub_items'] as List<dynamic>?)
              ?.map((e) => FutureViewSuggestionSubItem.fromJson(
                  e as Map<String, dynamic>))
              .toList() ??
          const [],
      actionOptions: ActionOptionModel.parseList(json['action_options']),
      groupKey: json['group_key'] as String? ?? '',
      groupLabel: json['group_label'] as String? ?? '',
    );
  }
}

class FutureViewUpcomingModel {
  final String id;
  final String title;
  final String emoji;
  final String dateLabel;
  final String contextHint;
  final int daysUntil;
  final String dotColor;
  final String dateType;

  const FutureViewUpcomingModel({
    required this.id,
    required this.title,
    required this.emoji,
    required this.dateLabel,
    required this.contextHint,
    required this.daysUntil,
    required this.dotColor,
    required this.dateType,
  });

  Color get dotColorValue => _parseHex(dotColor);

  factory FutureViewUpcomingModel.fromJson(Map<String, dynamic> json) {
    return FutureViewUpcomingModel(
      id: json['id'] as String,
      title: json['title'] as String,
      emoji: json['emoji'] as String? ?? '',
      dateLabel: json['date_label'] as String? ?? '',
      contextHint: json['context_hint'] as String? ?? '',
      daysUntil: json['days_until'] as int? ?? 0,
      dotColor: json['dot_color'] as String? ?? '#9C9B99',
      dateType: json['date_type'] as String? ?? '',
    );
  }
}

class FutureViewMemberModel {
  final String id;
  final String name;
  final String relationship;
  final String statusLine;
  final String avatarColor;
  final String avatarInitial;

  const FutureViewMemberModel({
    required this.id,
    required this.name,
    required this.relationship,
    required this.statusLine,
    required this.avatarColor,
    required this.avatarInitial,
  });

  Color get avatarColorValue => _parseHex(avatarColor);

  factory FutureViewMemberModel.fromJson(Map<String, dynamic> json) {
    return FutureViewMemberModel(
      id: json['id'] as String,
      name: json['name'] as String,
      relationship: json['relationship'] as String? ?? '',
      statusLine: json['status_line'] as String? ?? '',
      avatarColor: json['avatar_color'] as String? ?? '#9C9B99',
      avatarInitial: json['avatar_initial'] as String? ?? '',
    );
  }
}

class FutureViewResponseModel {
  final List<FutureViewTripModel> trips;
  final List<FutureViewSuggestionModel> suggestions;
  final List<FutureViewUpcomingModel> upcoming;
  final bool upcomingHasMore;
  final List<FutureViewMemberModel> familyMembers;

  const FutureViewResponseModel({
    required this.trips,
    required this.suggestions,
    required this.upcoming,
    this.upcomingHasMore = false,
    required this.familyMembers,
  });

  FutureViewResponseModel copyWith({
    List<FutureViewTripModel>? trips,
  }) {
    return FutureViewResponseModel(
      trips: trips ?? this.trips,
      suggestions: suggestions,
      upcoming: upcoming,
      upcomingHasMore: upcomingHasMore,
      familyMembers: familyMembers,
    );
  }

  FutureViewResponseModel copyWithMoreUpcoming(
    List<FutureViewUpcomingModel> moreItems,
    bool hasMore,
  ) {
    return FutureViewResponseModel(
      trips: trips,
      suggestions: suggestions,
      upcoming: [...upcoming, ...moreItems],
      upcomingHasMore: hasMore,
      familyMembers: familyMembers,
    );
  }

  factory FutureViewResponseModel.fromJson(Map<String, dynamic> json) {
    return FutureViewResponseModel(
      trips: (json['trips'] as List<dynamic>?)
              ?.map((e) =>
                  FutureViewTripModel.fromJson(e as Map<String, dynamic>))
              .toList() ??
          const [],
      suggestions: (json['suggestions'] as List<dynamic>?)
              ?.map((e) =>
                  FutureViewSuggestionModel.fromJson(e as Map<String, dynamic>))
              .toList() ??
          const [],
      upcoming: (json['upcoming'] as List<dynamic>?)
              ?.map((e) =>
                  FutureViewUpcomingModel.fromJson(e as Map<String, dynamic>))
              .toList() ??
          const [],
      upcomingHasMore: json['upcoming_has_more'] as bool? ?? false,
      familyMembers: (json['family_members'] as List<dynamic>?)
              ?.map((e) =>
                  FutureViewMemberModel.fromJson(e as Map<String, dynamic>))
              .toList() ??
          const [],
    );
  }
}

/// A group of suggestions sharing the same [groupKey].
class SuggestionGroup {
  final String groupKey;
  final String groupLabel;
  final List<FutureViewSuggestionModel> suggestions;

  const SuggestionGroup({
    required this.groupKey,
    required this.groupLabel,
    required this.suggestions,
  });

  bool get isSingleItem => suggestions.length == 1;

  /// All insight/suggestion IDs in this group (for batch dismiss).
  List<String> get allInsightIds => suggestions
      .map((s) => s.insightId.isNotEmpty ? s.insightId : s.id)
      .toList();
}

/// Group suggestions by [FutureViewSuggestionModel.groupKey].
///
/// Preserves first-occurrence order. Suggestions with empty groupKey
/// are each placed in their own single-item group.
List<SuggestionGroup> groupSuggestionsByKey(
  List<FutureViewSuggestionModel> suggestions,
) {
  if (suggestions.isEmpty) return const [];

  // Use LinkedHashMap behavior (Dart's default Map preserves insertion order)
  final Map<String, List<FutureViewSuggestionModel>> grouped = {};
  int emptyKeyCounter = 0;

  for (final s in suggestions) {
    final key = s.groupKey.isEmpty ? '__empty_${emptyKeyCounter++}' : s.groupKey;
    (grouped[key] ??= []).add(s);
  }

  return grouped.entries.map((entry) {
    final items = entry.value;
    return SuggestionGroup(
      groupKey: items.first.groupKey,
      groupLabel: items.first.groupLabel.isNotEmpty
          ? items.first.groupLabel
          : items.first.title,
      suggestions: items,
    );
  }).toList();
}
