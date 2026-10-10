import 'package:equatable/equatable.dart';

/// A single event in the daily briefing.
class BriefingEvent extends Equatable {
  final String id;
  final String title;
  final String? time; // "09:00" or "全天"
  final String icon;
  final String? description;
  final String? actionLabel;
  final String eventType;
  final String? memberId;
  final String? memberName;

  const BriefingEvent({
    required this.id,
    required this.title,
    this.time,
    required this.icon,
    this.description,
    this.actionLabel,
    this.eventType = 'general',
    this.memberId,
    this.memberName,
  });

  @override
  List<Object?> get props => [
        id,
        title,
        time,
        icon,
        description,
        actionLabel,
        eventType,
        memberId,
        memberName,
      ];

  /// Check if this is an all-day event
  bool get isAllDay => time == null || time == '全天';

  /// Get display time string
  String get displayTime => time ?? '全天';
}

/// Day theme describing the overall tone/focus of the day.
class DayTheme extends Equatable {
  final String title;
  final String? primaryEventId;
  final String focus;
  final String? prepNote;
  final String? eveningForward;

  const DayTheme({
    required this.title,
    this.primaryEventId,
    required this.focus,
    this.prepNote,
    this.eveningForward,
  });

  @override
  List<Object?> get props => [
        title,
        primaryEventId,
        focus,
        prepNote,
        eveningForward,
      ];
}

/// Secretary annotation attached to a briefing event.
class SecretaryAnnotation extends Equatable {
  final String eventId;
  final String text;
  final String source; // "context_enricher" | "priority_engine" | "preparation_timeline"

  const SecretaryAnnotation({
    required this.eventId,
    required this.text,
    required this.source,
  });

  @override
  List<Object?> get props => [eventId, text, source];
}

/// Insight surfaced in the daily briefing.
class BriefingInsight extends Equatable {
  final String id;
  final String insightType;
  final String title;
  final String content;
  final int priority;
  final String urgency;
  final List<String> actionOptions;
  final Map<String, dynamic> actionData;

  const BriefingInsight({
    required this.id,
    required this.insightType,
    required this.title,
    required this.content,
    this.priority = 5,
    this.urgency = 'normal',
    this.actionOptions = const [],
    this.actionData = const {},
  });

  @override
  List<Object?> get props => [
        id,
        insightType,
        title,
        content,
        priority,
        urgency,
        actionOptions,
        actionData,
      ];

  bool get isHighPriority => priority >= 7;
  bool get isUrgent => urgency == 'high';
}

/// A time slot in the day's schedule.
class TimeSlot extends Equatable {
  final String start;
  final String end;
  final String? eventId;
  final String slotType; // event | buffer | travel | free | preparation | recovery
  final String? note;

  const TimeSlot({
    required this.start,
    required this.end,
    this.eventId,
    required this.slotType,
    this.note,
  });

  @override
  List<Object?> get props => [start, end, eventId, slotType, note];

  bool get isFree => slotType == 'free';
  bool get isEvent => slotType == 'event';
}

/// Household status item for family overview.
class HouseholdStatus extends Equatable {
  final String id;
  final String title;
  final String description;
  final String icon;
  final String urgency;
  final String? actionLabel;

  const HouseholdStatus({
    required this.id,
    required this.title,
    required this.description,
    required this.icon,
    this.urgency = 'normal',
    this.actionLabel,
  });

  @override
  List<Object?> get props => [id, title, description, icon, urgency, actionLabel];

  bool get isUrgent => urgency == 'high';
}

/// Upcoming trip summary for briefing.
class UpcomingTrip extends Equatable {
  final String tripId;
  final String? tripName;
  final String destination;
  final DateTime startDate;
  final DateTime endDate;
  final String tripType;
  final String status;

  const UpcomingTrip({
    required this.tripId,
    this.tripName,
    required this.destination,
    required this.startDate,
    required this.endDate,
    this.tripType = 'leisure',
    this.status = 'planning',
  });

  @override
  List<Object?> get props => [
        tripId,
        tripName,
        destination,
        startDate,
        endDate,
        tripType,
        status,
      ];

  int get daysUntilStart {
    final now = DateTime.now();
    final diff = startDate.difference(DateTime(now.year, now.month, now.day)).inDays;
    return diff < 0 ? 0 : diff;
  }

  bool get isImminent => daysUntilStart <= 3;
}

/// Secretary-style alert for daily briefing (时间冲突/待办提醒等).
class BriefingAlert extends Equatable {
  final String id;
  final String alertType; // "conflict", "blocking", "change", "deadline"
  final String severity; // "info", "warning", "critical"
  final String title;
  final String description;
  final List<String> relatedEventIds;
  final String? actionLabel;
  final String icon;

  const BriefingAlert({
    required this.id,
    required this.alertType,
    this.severity = 'warning',
    required this.title,
    required this.description,
    this.relatedEventIds = const [],
    this.actionLabel,
    this.icon = '⚠️',
  });

  @override
  List<Object?> get props => [
        id,
        alertType,
        severity,
        title,
        description,
        relatedEventIds,
        actionLabel,
        icon,
      ];

  /// Check if this is a critical alert
  bool get isCritical => severity == 'critical';

  /// Check if this is a conflict alert
  bool get isConflict => alertType == 'conflict';

  /// Check if this is a soft suggestion (not an alarm)
  bool get isSuggestion => severity == 'suggestion';

  /// Get severity color
  int get severityColorValue {
    switch (severity) {
      case 'critical':
        return 0xFFE53935; // Red
      case 'warning':
        return 0xFFFB8C00; // Orange
      case 'suggestion':
        return 0xFF4A90D9; // Soft blue
      default:
        return 0xFF1E88E5; // Blue
    }
  }
}

/// A structured suggestion chip with action routing data.
class BriefingSuggestion extends Equatable {
  final String label;
  final String actionType;
  final Map<String, dynamic> actionData;

  const BriefingSuggestion({
    required this.label,
    required this.actionType,
    this.actionData = const {},
  });

  @override
  List<Object?> get props => [label, actionType, actionData];
}

/// Daily briefing containing all events and reminders for the day.
class DailyBriefing extends Equatable {
  final DateTime date;
  final String greeting;
  final String period;
  final int todayEventCount;
  final List<BriefingEvent> todayEvents;
  final List<String> preparationReminders;
  final int weekRemainingCount;
  final List<BriefingSuggestion> smartSuggestions;
  // Secretary-style alerts
  final List<BriefingAlert> alerts;
  // New fields from backend
  final DayTheme? dayTheme;
  final List<SecretaryAnnotation> annotations;
  final String? secretarySummary;
  final String densityLevel; // "FOCUSED" | "STANDARD" | "RELAXED" | "REFLECTIVE"
  final double densityScore;
  final int deferredCount;
  final List<String>? suggestedReorder;
  final List<BriefingInsight> insights;
  final List<HouseholdStatus> householdStatus;
  final List<UpcomingTrip> upcomingTrips;
  final List<BriefingEvent> tomorrowPreview;
  final List<TimeSlot> timeSlots;

  const DailyBriefing({
    required this.date,
    required this.greeting,
    this.period = 'morning',
    required this.todayEventCount,
    required this.todayEvents,
    required this.preparationReminders,
    required this.weekRemainingCount,
    required this.smartSuggestions,
    this.alerts = const [],
    this.dayTheme,
    this.annotations = const [],
    this.secretarySummary,
    this.densityLevel = 'STANDARD',
    this.densityScore = 0.0,
    this.deferredCount = 0,
    this.suggestedReorder,
    this.insights = const [],
    this.householdStatus = const [],
    this.upcomingTrips = const [],
    this.tomorrowPreview = const [],
    this.timeSlots = const [],
  });

  @override
  List<Object?> get props => [
        date,
        greeting,
        period,
        todayEventCount,
        todayEvents,
        preparationReminders,
        weekRemainingCount,
        smartSuggestions,
        alerts,
        dayTheme,
        annotations,
        secretarySummary,
        densityLevel,
        densityScore,
        deferredCount,
        suggestedReorder,
        insights,
        householdStatus,
        upcomingTrips,
        tomorrowPreview,
        timeSlots,
      ];

  /// Check if there are events today
  bool get hasEventsToday => todayEventCount > 0;

  /// Check if there are preparation reminders
  bool get hasReminders => preparationReminders.isNotEmpty;

  /// Check if there are alerts
  bool get hasAlerts => alerts.isNotEmpty;

  /// Check if there is a day theme
  bool get hasDayTheme => dayTheme != null;

  /// Check if the day is busy (FOCUSED = high density from backend)
  bool get isBusy => densityLevel == 'FOCUSED';

  /// Whether to use focused display mode (show fewer items, prioritize)
  bool get isFocused => densityLevel == 'FOCUSED';

  /// Whether to use relaxed display mode (show more, expand)
  bool get isRelaxed => densityLevel == 'RELAXED' || densityLevel == 'REFLECTIVE';

  /// Get annotations for a specific event
  List<SecretaryAnnotation> annotationsForEvent(String eventId) {
    return annotations.where((a) => a.eventId == eventId).toList();
  }

  /// Get events ordered by suggested_reorder (for FOCUSED mode)
  List<BriefingEvent> get orderedEvents {
    if (suggestedReorder == null || suggestedReorder!.isEmpty) {
      return todayEvents;
    }
    final orderMap = <String, int>{};
    for (var i = 0; i < suggestedReorder!.length; i++) {
      orderMap[suggestedReorder![i]] = i;
    }
    final sorted = List<BriefingEvent>.from(todayEvents);
    sorted.sort((a, b) {
      final orderA = orderMap[a.id] ?? 999;
      final orderB = orderMap[b.id] ?? 999;
      return orderA.compareTo(orderB);
    });
    return sorted;
  }

  /// Get recovery/buffer time slots
  List<TimeSlot> get recoverySlots {
    return timeSlots.where((s) =>
      s.slotType == 'buffer' ||
      s.slotType == 'recovery' ||
      s.slotType == 'free'
    ).toList();
  }

  /// Check if there are insights
  bool get hasInsights => insights.isNotEmpty;

  /// Check if there are upcoming trips
  bool get hasUpcomingTrips => upcomingTrips.isNotEmpty;

  /// Check if there is a tomorrow preview
  bool get hasTomorrowPreview => tomorrowPreview.isNotEmpty;

  /// Get formatted date string
  String get formattedDate {
    final month = date.month;
    final day = date.day;
    final weekday = _getWeekdayName(date.weekday);
    return '$month月$day日 $weekday';
  }

  String _getWeekdayName(int weekday) {
    const weekdays = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'];
    return weekdays[weekday - 1];
  }

  /// Factory for creating an empty briefing
  /// PRD 4.3: 使用"老板"称呼
  factory DailyBriefing.empty() {
    final hour = DateTime.now().hour;
    String period;
    String greeting;
    if (hour < 6 || hour >= 22) {
      period = 'evening';
      greeting = '🌙 夜深了，老板';
    } else if (hour < 9) {
      period = 'morning';
      greeting = '☀️ 早安，老板';
    } else if (hour < 12) {
      period = 'morning';
      greeting = '🌤️ 上午好，老板';
    } else if (hour < 14) {
      period = 'afternoon';
      greeting = '🌞 中午好，老板';
    } else if (hour < 18) {
      period = 'afternoon';
      greeting = '⛅ 下午好，老板';
    } else {
      period = 'evening';
      greeting = '🌆 晚上好，老板';
    }

    return DailyBriefing(
      date: DateTime.now(),
      greeting: greeting,
      period: period,
      todayEventCount: 0,
      todayEvents: const [],
      preparationReminders: const [],
      weekRemainingCount: 0,
      smartSuggestions: const <BriefingSuggestion>[],
      alerts: const [],
      annotations: const [],
      insights: const [],
      householdStatus: const [],
      upcomingTrips: const [],
      tomorrowPreview: const [],
      timeSlots: const [],
    );
  }
}
