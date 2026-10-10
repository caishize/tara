import '../../../../core/utils/timezone_utils.dart';
import '../../domain/entities/memory_lane.dart';

/// Parse an OnThisDayItem from JSON
class OnThisDayItemModel extends OnThisDayItem {
  const OnThisDayItemModel({
    required super.id,
    required super.title,
    super.eventType,
    required super.year,
    super.startTime,
    super.location,
    super.notes,
    super.tripId,
    super.tripName,
    super.coverImageUrl,
    super.participantCount,
    super.durationDays,
    super.memorySummaries,
  });

  factory OnThisDayItemModel.fromJson(Map<String, dynamic> json) {
    return OnThisDayItemModel(
      id: json['id'] as String? ?? '',
      title: json['title'] as String? ?? '',
      eventType: json['event_type'] as String?,
      year: json['year'] as int? ?? 0,
      startTime: json['start_time'] != null
          ? TimezoneUtils.parseApiTime(json['start_time'] as String)
          : null,
      location: json['location'] as String?,
      notes: json['notes'] as String?,
      tripId: json['trip_id'] as String?,
      tripName: json['trip_name'] as String?,
      coverImageUrl: json['cover_image_url'] as String?,
      participantCount: json['participant_count'] as int? ?? 0,
      durationDays: json['duration_days'] as int? ?? 1,
      memorySummaries: (json['memory_summaries'] as List<dynamic>?)
          ?.map((e) => e.toString())
          .toList() ?? const [],
    );
  }
}

/// Parse OnThisDayResponse from JSON
class OnThisDayResponseModel extends OnThisDayResponse {
  const OnThisDayResponseModel({
    required super.items,
    required super.month,
    required super.day,
  });

  factory OnThisDayResponseModel.fromJson(Map<String, dynamic> json) {
    final itemsJson = json['items'] as List<dynamic>? ?? [];
    return OnThisDayResponseModel(
      items: itemsJson
          .map((e) => OnThisDayItemModel.fromJson(e as Map<String, dynamic>))
          .toList(),
      month: json['month'] as int? ?? 1,
      day: json['day'] as int? ?? 1,
    );
  }
}

/// Parse a StoryParticipant from JSON
class StoryParticipantModel extends StoryParticipant {
  const StoryParticipantModel({
    required super.name,
    super.avatarColor,
  });

  factory StoryParticipantModel.fromJson(Map<String, dynamic> json) {
    return StoryParticipantModel(
      name: json['name'] as String? ?? '',
      avatarColor: json['avatar_color'] as String?,
    );
  }
}

/// Parse a StoryEvent from JSON (backend KanbanEvent shape)
class StoryEventModel extends StoryEvent {
  const StoryEventModel({
    required super.id,
    required super.title,
    super.eventType,
    super.startTime,
    super.endTime,
    super.location,
    super.status,
    super.priority,
    super.notes,
    super.tripId,
    super.tripName,
    super.speaker,
    super.photoUrls,
    super.secretaryNote,
    super.isPinned,
  });

  factory StoryEventModel.fromJson(Map<String, dynamic> json) {
    return StoryEventModel(
      id: json['id'] as String? ?? '',
      title: json['title'] as String? ?? '',
      eventType: json['event_type'] as String?,
      startTime: json['start_time'] != null
          ? TimezoneUtils.parseApiTime(json['start_time'] as String)
          : null,
      endTime: json['end_time'] != null
          ? TimezoneUtils.parseApiTime(json['end_time'] as String)
          : null,
      location: json['location'] as String?,
      status: json['status'] as String?,
      priority: json['priority'] as String?,
      notes: json['notes'] as String?,
      tripId: json['trip_id'] as String?,
      tripName: json['trip_name'] as String?,
      speaker: json['speaker'] as String?,
      photoUrls: (json['photo_urls'] as List<dynamic>?)
          ?.map((e) => e.toString())
          .toList() ?? const [],
      secretaryNote: json['secretary_note'] as String?,
      isPinned: json['is_pinned'] as bool? ?? false,
    );
  }
}

/// Parse a StoryGroup from JSON
class StoryGroupModel extends StoryGroup {
  const StoryGroupModel({
    super.tripId,
    required super.title,
    required super.events,
    super.memorySummaries,
    super.startDate,
    super.endDate,
    super.participantCount,
    super.participants,
    super.emotionalTag,
  });

  factory StoryGroupModel.fromJson(Map<String, dynamic> json) {
    final eventsJson = json['events'] as List<dynamic>? ?? [];
    final memoriesJson = json['memory_summaries'] as List<dynamic>? ?? [];
    final participantsJson = json['participants'] as List<dynamic>? ?? [];
    return StoryGroupModel(
      tripId: json['trip_id'] as String?,
      title: json['title'] as String? ?? '',
      events: eventsJson
          .map((e) => StoryEventModel.fromJson(e as Map<String, dynamic>))
          .toList(),
      memorySummaries: memoriesJson.map((e) => e.toString()).toList(),
      startDate: json['start_date'] != null
          ? DateTime.tryParse(json['start_date'] as String)
          : null,
      endDate: json['end_date'] != null
          ? DateTime.tryParse(json['end_date'] as String)
          : null,
      participantCount: json['participant_count'] as int? ?? 0,
      participants: participantsJson
          .map((e) => StoryParticipantModel.fromJson(e as Map<String, dynamic>))
          .toList(),
      emotionalTag: json['emotional_tag'] as String?,
    );
  }
}

/// Parse a YearlySummary from JSON (backend YearGroup)
class YearlySummaryModel extends YearlySummary {
  const YearlySummaryModel({
    required super.year,
    super.stories,
    super.eventCount,
  });

  factory YearlySummaryModel.fromJson(Map<String, dynamic> json) {
    final storiesJson = json['stories'] as List<dynamic>? ?? [];
    return YearlySummaryModel(
      year: json['year'] as int? ?? 0,
      stories: storiesJson
          .map((e) => StoryGroupModel.fromJson(e as Map<String, dynamic>))
          .toList(),
      eventCount: json['event_count'] as int? ?? 0,
    );
  }
}

/// Parse MemoryLaneResponse from JSON
class MemoryLaneResponseModel extends MemoryLaneResponse {
  const MemoryLaneResponseModel({
    super.years,
    super.totalEvents,
  });

  factory MemoryLaneResponseModel.fromJson(Map<String, dynamic> json) {
    final yearsJson = json['years'] as List<dynamic>? ?? [];
    return MemoryLaneResponseModel(
      years: yearsJson
          .map((e) => YearlySummaryModel.fromJson(e as Map<String, dynamic>))
          .toList(),
      totalEvents: json['total_events'] as int? ?? 0,
    );
  }
}
