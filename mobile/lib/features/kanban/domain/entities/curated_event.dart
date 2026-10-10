import 'package:equatable/equatable.dart';

/// 时间线子项 (跨天事件的具体时间点)
class TimelineItem extends Equatable {
  final String time;
  final String item;
  final bool confirmed;
  final String? note;

  const TimelineItem({
    required this.time,
    required this.item,
    this.confirmed = true,
    this.note,
  });

  @override
  List<Object?> get props => [time, item, confirmed, note];
}

/// 事件类型枚举
enum CuratedEventType {
  businessTrip,
  travel,
  meeting,
  appointment,
  reminder,
  birthday,
  anniversary,
  holiday,
  other;

  static CuratedEventType fromString(String? value) {
    switch (value) {
      case 'business_trip':
        return CuratedEventType.businessTrip;
      case 'travel':
        return CuratedEventType.travel;
      case 'meeting':
        return CuratedEventType.meeting;
      case 'appointment':
        return CuratedEventType.appointment;
      case 'reminder':
        return CuratedEventType.reminder;
      case 'birthday':
        return CuratedEventType.birthday;
      case 'anniversary':
        return CuratedEventType.anniversary;
      case 'holiday':
        return CuratedEventType.holiday;
      default:
        return CuratedEventType.other;
    }
  }

  String get displayName {
    switch (this) {
      case CuratedEventType.businessTrip:
        return '出差';
      case CuratedEventType.travel:
        return '旅行';
      case CuratedEventType.meeting:
        return '会议';
      case CuratedEventType.appointment:
        return '预约';
      case CuratedEventType.reminder:
        return '提醒';
      case CuratedEventType.birthday:
        return '生日';
      case CuratedEventType.anniversary:
        return '纪念日';
      case CuratedEventType.holiday:
        return '节日';
      case CuratedEventType.other:
        return '其他';
    }
  }

  String get icon {
    switch (this) {
      case CuratedEventType.businessTrip:
        return '💼';
      case CuratedEventType.travel:
        return '✈️';
      case CuratedEventType.meeting:
        return '🤝';
      case CuratedEventType.appointment:
        return '📅';
      case CuratedEventType.reminder:
        return '⏰';
      case CuratedEventType.birthday:
        return '🎂';
      case CuratedEventType.anniversary:
        return '💑';
      case CuratedEventType.holiday:
        return '🎉';
      case CuratedEventType.other:
        return '📌';
    }
  }

  /// Primary color for the event type
  int get colorValue {
    switch (this) {
      case CuratedEventType.businessTrip:
        return 0xFF4A90D9; // Business blue
      case CuratedEventType.travel:
        return 0xFF26A69A; // Travel teal
      case CuratedEventType.meeting:
        return 0xFF5C6BC0; // Meeting purple
      case CuratedEventType.appointment:
        return 0xFF42A5F5; // Appointment blue
      case CuratedEventType.reminder:
        return 0xFFFFB300; // Reminder amber
      case CuratedEventType.birthday:
        return 0xFFEC407A; // Birthday pink
      case CuratedEventType.anniversary:
        return 0xFFEF5350; // Anniversary red
      case CuratedEventType.holiday:
        return 0xFFFF7043; // Holiday orange
      case CuratedEventType.other:
        return 0xFF78909C; // Other grey
    }
  }
}

/// AI整理后的事件实体
class CuratedEvent extends Equatable {
  final String id;
  final String title;
  final CuratedEventType? eventType;
  final DateTime startTime;
  final DateTime? endTime;
  final String? location;
  final String? notes;
  final String? priority;
  final List<TimelineItem> timelineItems;
  final List<String> sourceTypes;
  final List<String> originalEventIds;
  final int mergedCount;
  final String? dedupReason;
  final double confidence;
  final Map<String, dynamic>? enrichments;
  final String? tripId;
  final String? tripName;
  final String? tripDayLabel;
  // Secretary-style enhancements
  final bool hasConflict;
  final List<String> conflictWith;
  final int? sequenceOfDay;

  const CuratedEvent({
    required this.id,
    required this.title,
    this.eventType,
    required this.startTime,
    this.endTime,
    this.location,
    this.notes,
    this.priority,
    this.timelineItems = const [],
    this.sourceTypes = const [],
    this.originalEventIds = const [],
    this.mergedCount = 1,
    this.dedupReason,
    this.confidence = 0.8,
    this.enrichments,
    this.tripId,
    this.tripName,
    this.tripDayLabel,
    this.hasConflict = false,
    this.conflictWith = const [],
    this.sequenceOfDay,
  });

  /// Whether this event belongs to a trip
  bool get belongsToTrip => tripId != null && tripName != null;

  /// 是否为多天事件 (使用本地时间比较)
  bool get isMultiDay {
    if (endTime == null) return false;
    // Convert to local time for accurate day comparison
    final localStart = startTime.toLocal();
    final localEnd = endTime!.toLocal();
    return localStart.day != localEnd.day ||
        localStart.month != localEnd.month ||
        localStart.year != localEnd.year;
  }

  /// 是否有未确认的子项
  bool get hasUnconfirmedItems {
    return timelineItems.any((item) => !item.confirmed);
  }

  /// 未确认子项数量
  int get unconfirmedCount {
    return timelineItems.where((item) => !item.confirmed).length;
  }

  /// 事件时长(天)
  int get durationDays {
    if (endTime == null) return 1;
    return endTime!.difference(startTime).inDays + 1;
  }

  @override
  List<Object?> get props => [
        id,
        title,
        eventType,
        startTime,
        endTime,
        location,
        notes,
        priority,
        timelineItems,
        sourceTypes,
        originalEventIds,
        mergedCount,
        dedupReason,
        confidence,
        enrichments,
        tripId,
        tripName,
        tripDayLabel,
        hasConflict,
        conflictWith,
        sequenceOfDay,
      ];
}

/// 待确认项
class UnconfirmedItem extends Equatable {
  final String eventId;
  final String item;
  final String question;

  const UnconfirmedItem({
    required this.eventId,
    required this.item,
    required this.question,
  });

  @override
  List<Object?> get props => [eventId, item, question];
}

/// AI整理后的时光轴数据
class CuratedTimeline extends Equatable {
  final List<CuratedEvent> events;
  final DateTime? lastCuratedAt;
  final bool hasUnconfirmed;
  final int unconfirmedCount;
  final List<UnconfirmedItem> unconfirmedItems;

  const CuratedTimeline({
    required this.events,
    this.lastCuratedAt,
    this.hasUnconfirmed = false,
    this.unconfirmedCount = 0,
    this.unconfirmedItems = const [],
  });

  /// 按日期分组事件 (使用本地时间)
  Map<DateTime, List<CuratedEvent>> get eventsByDate {
    final map = <DateTime, List<CuratedEvent>>{};
    for (final event in events) {
      // Convert to local time for grouping
      final localStart = event.startTime.toLocal();
      final dateKey = DateTime(
        localStart.year,
        localStart.month,
        localStart.day,
      );
      map.putIfAbsent(dateKey, () => []).add(event);
    }
    return map;
  }

  /// 按事件类型分组 (用于出差等多天事件的段落显示)
  Map<CuratedEventType, List<CuratedEvent>> get eventsByType {
    final map = <CuratedEventType, List<CuratedEvent>>{};
    for (final event in events) {
      final type = event.eventType ?? CuratedEventType.other;
      map.putIfAbsent(type, () => []).add(event);
    }
    return map;
  }

  @override
  List<Object?> get props => [
        events,
        lastCuratedAt,
        hasUnconfirmed,
        unconfirmedCount,
        unconfirmedItems,
      ];
}
