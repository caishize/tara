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

  /// Get severity color
  int get severityColorValue {
    switch (severity) {
      case 'critical':
        return 0xFFE53935; // Red
      case 'warning':
        return 0xFFFB8C00; // Orange
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
  final int todayEventCount;
  final List<BriefingEvent> todayEvents;
  final List<String> preparationReminders;
  final int weekRemainingCount;
  final List<BriefingSuggestion> smartSuggestions;
  // Secretary-style alerts
  final List<BriefingAlert> alerts;

  const DailyBriefing({
    required this.date,
    required this.greeting,
    required this.todayEventCount,
    required this.todayEvents,
    required this.preparationReminders,
    required this.weekRemainingCount,
    required this.smartSuggestions,
    this.alerts = const [],
  });

  @override
  List<Object?> get props => [
        date,
        greeting,
        todayEventCount,
        todayEvents,
        preparationReminders,
        weekRemainingCount,
        smartSuggestions,
        alerts,
      ];

  /// Check if there are events today
  bool get hasEventsToday => todayEventCount > 0;

  /// Check if there are preparation reminders
  bool get hasReminders => preparationReminders.isNotEmpty;

  /// Check if there are alerts
  bool get hasAlerts => alerts.isNotEmpty;

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
    String greeting;
    if (hour < 6 || hour >= 22) {
      greeting = '🌙 夜深了，老板';
    } else if (hour < 9) {
      greeting = '☀️ 早安，老板';
    } else if (hour < 12) {
      greeting = '🌤️ 上午好，老板';
    } else if (hour < 14) {
      greeting = '🌞 中午好，老板';
    } else if (hour < 18) {
      greeting = '⛅ 下午好，老板';
    } else {
      greeting = '🌆 晚上好，老板';
    }

    return DailyBriefing(
      date: DateTime.now(),
      greeting: greeting,
      todayEventCount: 0,
      todayEvents: const [],
      preparationReminders: const [],
      weekRemainingCount: 0,
      smartSuggestions: const <BriefingSuggestion>[],
      alerts: const [],
    );
  }
}

