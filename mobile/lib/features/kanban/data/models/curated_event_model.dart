import '../../../../core/utils/timezone_utils.dart';

import '../../domain/entities/curated_event.dart';

/// TimelineItem 数据模型
class TimelineItemModel extends TimelineItem {
  const TimelineItemModel({
    required super.time,
    required super.item,
    super.confirmed = true,
    super.note,
  });

  factory TimelineItemModel.fromJson(Map<String, dynamic> json) {
    return TimelineItemModel(
      time: json['time'] as String? ?? '',
      item: json['item'] as String? ?? '',
      confirmed: json['confirmed'] as bool? ?? true,
      note: json['note'] as String?,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'time': time,
      'item': item,
      'confirmed': confirmed,
      'note': note,
    };
  }

  factory TimelineItemModel.fromEntity(TimelineItem entity) {
    return TimelineItemModel(
      time: entity.time,
      item: entity.item,
      confirmed: entity.confirmed,
      note: entity.note,
    );
  }
}

/// CuratedEvent 数据模型
class CuratedEventModel extends CuratedEvent {
  const CuratedEventModel({
    required super.id,
    required super.title,
    super.eventType,
    required super.startTime,
    super.endTime,
    super.location,
    super.notes,
    super.priority,
    super.timelineItems = const [],
    super.sourceTypes = const [],
    super.originalEventIds = const [],
    super.mergedCount = 1,
    super.dedupReason,
    super.confidence = 0.8,
    super.enrichments,
    super.tripId,
    super.tripName,
    super.tripDayLabel,
    super.hasConflict = false,
    super.conflictWith = const [],
    super.sequenceOfDay,
  });

  factory CuratedEventModel.fromJson(Map<String, dynamic> json) {
    return CuratedEventModel(
      id: json['id'] as String? ?? '',
      title: json['title'] as String? ?? '',
      eventType: CuratedEventType.fromString(json['event_type'] as String?),
      startTime: _parseDateTime(json['start_time']),
      endTime: json['end_time'] != null
          ? _parseDateTime(json['end_time'])
          : null,
      location: json['location'] as String?,
      notes: json['notes'] as String?,
      priority: json['priority'] as String?,
      timelineItems: (json['timeline_items'] as List<dynamic>?)
              ?.map((e) => TimelineItemModel.fromJson(e as Map<String, dynamic>))
              .toList() ??
          const [],
      sourceTypes: (json['source_types'] as List<dynamic>?)
              ?.map((e) => e.toString())
              .toList() ??
          const [],
      originalEventIds: (json['original_event_ids'] as List<dynamic>?)
              ?.map((e) => e.toString())
              .toList() ??
          const [],
      mergedCount: json['merged_count'] as int? ?? 1,
      dedupReason: json['dedup_reason'] as String?,
      confidence: (json['confidence'] as num?)?.toDouble() ?? 0.8,
      enrichments: json['enrichments'] as Map<String, dynamic>?,
      tripId: json['trip_id'] as String?,
      tripName: json['trip_name'] as String?,
      tripDayLabel: json['trip_day_label'] as String?,
      hasConflict: json['has_conflict'] as bool? ?? false,
      conflictWith: (json['conflict_with'] as List<dynamic>?)
              ?.map((e) => e.toString())
              .toList() ??
          const [],
      sequenceOfDay: json['sequence_of_day'] as int?,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'title': title,
      'event_type': _eventTypeToString(eventType),
      'start_time': TimezoneUtils.toApiTime(startTime),
      'end_time': endTime != null ? TimezoneUtils.toApiTime(endTime!) : null,
      'location': location,
      'notes': notes,
      'priority': priority,
      'timeline_items': timelineItems.map((e) {
        if (e is TimelineItemModel) {
          return e.toJson();
        } else {
          return TimelineItemModel.fromEntity(e).toJson();
        }
      }).toList(),
      'source_types': sourceTypes,
      'original_event_ids': originalEventIds,
      'merged_count': mergedCount,
      'dedup_reason': dedupReason,
      'confidence': confidence,
      'enrichments': enrichments,
      'trip_id': tripId,
      'trip_name': tripName,
      'trip_day_label': tripDayLabel,
      'has_conflict': hasConflict,
      'conflict_with': conflictWith,
      'sequence_of_day': sequenceOfDay,
    };
  }

  factory CuratedEventModel.fromEntity(CuratedEvent entity) {
    return CuratedEventModel(
      id: entity.id,
      title: entity.title,
      eventType: entity.eventType,
      startTime: entity.startTime,
      endTime: entity.endTime,
      location: entity.location,
      notes: entity.notes,
      priority: entity.priority,
      timelineItems: entity.timelineItems
          .map((e) => TimelineItemModel.fromEntity(e))
          .toList(),
      sourceTypes: entity.sourceTypes,
      originalEventIds: entity.originalEventIds,
      mergedCount: entity.mergedCount,
      dedupReason: entity.dedupReason,
      confidence: entity.confidence,
      enrichments: entity.enrichments,
      tripId: entity.tripId,
      tripName: entity.tripName,
      tripDayLabel: entity.tripDayLabel,
      hasConflict: entity.hasConflict,
      conflictWith: entity.conflictWith,
      sequenceOfDay: entity.sequenceOfDay,
    );
  }

  static DateTime _parseDateTime(dynamic value) {
    if (value == null) return DateTime.now().toUtc();
    if (value is DateTime) return value.toUtc();
    if (value is String) {
      return TimezoneUtils.parseApiTime(value);
    }
    return DateTime.now().toUtc();
  }

  static const _eventTypeMap = {
    CuratedEventType.businessTrip: 'business_trip',
    CuratedEventType.travel: 'travel',
    CuratedEventType.meeting: 'meeting',
    CuratedEventType.appointment: 'appointment',
    CuratedEventType.reminder: 'reminder',
    CuratedEventType.birthday: 'birthday',
    CuratedEventType.anniversary: 'anniversary',
    CuratedEventType.holiday: 'holiday',
    CuratedEventType.other: 'other',
  };

  static String? _eventTypeToString(CuratedEventType? type) {
    if (type == null) return null;
    return _eventTypeMap[type];
  }
}

/// UnconfirmedItem 数据模型
class UnconfirmedItemModel extends UnconfirmedItem {
  const UnconfirmedItemModel({
    required super.eventId,
    required super.item,
    required super.question,
  });

  factory UnconfirmedItemModel.fromJson(Map<String, dynamic> json) {
    return UnconfirmedItemModel(
      eventId: json['event_id'] as String? ?? '',
      item: json['item'] as String? ?? '',
      question: json['question'] as String? ?? '',
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'event_id': eventId,
      'item': item,
      'question': question,
    };
  }
}

/// CuratedTimeline 数据模型
class CuratedTimelineModel extends CuratedTimeline {
  const CuratedTimelineModel({
    required super.events,
    super.lastCuratedAt,
    super.hasUnconfirmed = false,
    super.unconfirmedCount = 0,
    super.unconfirmedItems = const [],
  });

  factory CuratedTimelineModel.fromJson(Map<String, dynamic> json) {
    return CuratedTimelineModel(
      events: (json['events'] as List<dynamic>?)
              ?.map((e) => CuratedEventModel.fromJson(e as Map<String, dynamic>))
              .toList() ??
          const [],
      lastCuratedAt: json['last_curated_at'] != null
          ? TimezoneUtils.parseApiTime(json['last_curated_at'] as String)
          : null,
      hasUnconfirmed: json['has_unconfirmed'] as bool? ?? false,
      unconfirmedCount: json['unconfirmed_count'] as int? ?? 0,
      unconfirmedItems: (json['unconfirmed_items'] as List<dynamic>?)
              ?.map(
                  (e) => UnconfirmedItemModel.fromJson(e as Map<String, dynamic>))
              .toList() ??
          const [],
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'events': events.map((e) {
        if (e is CuratedEventModel) {
          return e.toJson();
        } else {
          return CuratedEventModel.fromEntity(e).toJson();
        }
      }).toList(),
      'last_curated_at': lastCuratedAt != null ? TimezoneUtils.toApiTime(lastCuratedAt!) : null,
      'has_unconfirmed': hasUnconfirmed,
      'unconfirmed_count': unconfirmedCount,
      'unconfirmed_items': unconfirmedItems.map((e) {
        if (e is UnconfirmedItemModel) {
          return e.toJson();
        } else {
          return UnconfirmedItemModel(
            eventId: e.eventId,
            item: e.item,
            question: e.question,
          ).toJson();
        }
      }).toList(),
    };
  }
}
