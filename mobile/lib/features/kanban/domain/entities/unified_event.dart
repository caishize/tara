import 'package:equatable/equatable.dart';
import 'package:flutter/material.dart';

/// Event source types
enum EventSource {
  importantDate,     // From dates module (birthdays, anniversaries, etc.)
  travelPlan,        // From travel module
  familyTask,        // From assistant module (family tasks/todos)
  extractedSchedule, // From secretary module (AI extracted schedules)
  extractedPlan,     // From secretary module (AI extracted plans)
  externalCalendar,  // From external calendars (Google, Outlook)
  externalTravel,    // From parsed travel emails (flights, hotels)
}

/// Extension to provide consistent colors and labels for event sources
extension EventSourceExtension on EventSource {
  /// Get the color for this event source
  Color get color {
    switch (this) {
      case EventSource.importantDate:
        return Colors.amber;
      case EventSource.travelPlan:
        return Colors.blue;
      case EventSource.familyTask:
        return Colors.indigo;
      case EventSource.extractedSchedule:
        return Colors.green;
      case EventSource.extractedPlan:
        return Colors.purple;
      case EventSource.externalCalendar:
        return Colors.teal;
      case EventSource.externalTravel:
        return Colors.orange;
    }
  }

  /// Get the display label for this event source
  String get label {
    switch (this) {
      case EventSource.importantDate:
        return '重要日期';
      case EventSource.travelPlan:
        return '旅行';
      case EventSource.familyTask:
        return '任务';
      case EventSource.extractedSchedule:
        return '日程';
      case EventSource.extractedPlan:
        return '计划';
      case EventSource.externalCalendar:
        return '外部日历';
      case EventSource.externalTravel:
        return '行程预订';
    }
  }
}

/// Time period grouping
enum TimePeriod {
  overdue,    // Past events
  today,      // Today
  tomorrow,   // Tomorrow
  thisWeek,   // This week (excluding today and tomorrow)
  nextWeek,   // Next week
  later,      // Further in the future
}

/// Unified event entity that aggregates events from different sources
class UnifiedEvent extends Equatable {
  final String id;
  final EventSource source;
  final String title;
  final DateTime? dateTime;
  final DateTime? endDateTime;  // For multi-day events like travel
  final String? location;
  final String? relatedMemberId;
  final String? memberName;
  final List<String> aiInsights;
  final Map<String, dynamic> sourceData;  // Original data from source
  final String icon;
  final Color color;
  final bool isAllDay;
  final String? description;

  const UnifiedEvent({
    required this.id,
    required this.source,
    required this.title,
    this.dateTime,
    this.endDateTime,
    this.location,
    this.relatedMemberId,
    this.memberName,
    this.aiInsights = const [],
    this.sourceData = const {},
    required this.icon,
    required this.color,
    this.isAllDay = true,
    this.description,
  });

  /// Get display name for event source
  String get sourceName {
    switch (source) {
      case EventSource.importantDate:
        return '重要日期';
      case EventSource.travelPlan:
        return '旅行计划';
      case EventSource.familyTask:
        return '待办任务';
      case EventSource.extractedSchedule:
        return '日程安排';
      case EventSource.extractedPlan:
        return '待办计划';
      case EventSource.externalCalendar:
        return '外部日历';
      case EventSource.externalTravel:
        return '行程预订';
    }
  }

  /// Get time period for this event
  TimePeriod get timePeriod {
    if (dateTime == null) return TimePeriod.later;

    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);
    // Convert to local time before extracting date components
    final localDateTime = dateTime!.toLocal();
    final eventDate = DateTime(localDateTime.year, localDateTime.month, localDateTime.day);
    final daysDiff = eventDate.difference(today).inDays;

    if (daysDiff < 0) return TimePeriod.overdue;
    if (daysDiff == 0) return TimePeriod.today;
    if (daysDiff == 1) return TimePeriod.tomorrow;
    if (daysDiff <= 7) return TimePeriod.thisWeek;
    if (daysDiff <= 14) return TimePeriod.nextWeek;
    return TimePeriod.later;
  }

  /// Days until the event (negative if in the past)
  int get daysUntil {
    if (dateTime == null) return 999;
    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);
    // Convert to local time before extracting date components
    final localDateTime = dateTime!.toLocal();
    final eventDate = DateTime(localDateTime.year, localDateTime.month, localDateTime.day);
    return eventDate.difference(today).inDays;
  }

  /// Check if event is today
  bool get isToday => daysUntil == 0;

  /// Check if event is in the past
  bool get isOverdue => daysUntil < 0;

  /// Duration in days for multi-day events
  int? get durationDays {
    if (dateTime == null || endDateTime == null) return null;
    return endDateTime!.difference(dateTime!).inDays + 1;
  }

  /// Get display string for countdown
  String get countdownDisplay {
    final days = daysUntil;
    if (days < 0) return '已过${-days}天';
    if (days == 0) return '今天';
    if (days == 1) return '明天';
    return '$days天后';
  }

  /// Check if this event occurs on a given date (for calendar view)
  bool occursOnDate(DateTime checkDate) {
    if (dateTime == null) return false;

    final startOfDay = DateTime(checkDate.year, checkDate.month, checkDate.day);
    // Convert to local time before extracting date components
    final localStart = dateTime!.toLocal();
    final eventStart = DateTime(localStart.year, localStart.month, localStart.day);

    if (endDateTime == null) {
      return startOfDay == eventStart;
    }

    // Convert end time to local as well
    final localEnd = endDateTime!.toLocal();
    final eventEnd = DateTime(localEnd.year, localEnd.month, localEnd.day);
    return !startOfDay.isBefore(eventStart) && !startOfDay.isAfter(eventEnd);
  }

  /// Check if event is upcoming (within 7 days)
  bool get isUpcoming {
    final days = daysUntil;
    return days > 0 && days <= 7;
  }

  UnifiedEvent copyWith({
    String? id,
    EventSource? source,
    String? title,
    DateTime? dateTime,
    DateTime? endDateTime,
    String? location,
    String? relatedMemberId,
    String? memberName,
    List<String>? aiInsights,
    Map<String, dynamic>? sourceData,
    String? icon,
    Color? color,
    bool? isAllDay,
    String? description,
  }) {
    return UnifiedEvent(
      id: id ?? this.id,
      source: source ?? this.source,
      title: title ?? this.title,
      dateTime: dateTime ?? this.dateTime,
      endDateTime: endDateTime ?? this.endDateTime,
      location: location ?? this.location,
      relatedMemberId: relatedMemberId ?? this.relatedMemberId,
      memberName: memberName ?? this.memberName,
      aiInsights: aiInsights ?? this.aiInsights,
      sourceData: sourceData ?? this.sourceData,
      icon: icon ?? this.icon,
      color: color ?? this.color,
      isAllDay: isAllDay ?? this.isAllDay,
      description: description ?? this.description,
    );
  }

  @override
  List<Object?> get props => [
    id, source, title, dateTime, endDateTime, location,
    relatedMemberId, memberName, aiInsights, sourceData,
    icon, color, isAllDay, description,
  ];
}
