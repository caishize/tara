import '../../../../core/utils/timezone_utils.dart';

import '../../domain/entities/daily_briefing.dart';

/// Model for BriefingEvent with JSON serialization.
class BriefingEventModel extends BriefingEvent {
  const BriefingEventModel({
    required super.id,
    required super.title,
    super.time,
    required super.icon,
    super.description,
    super.actionLabel,
    super.eventType,
    super.memberId,
    super.memberName,
  });

  factory BriefingEventModel.fromJson(Map<String, dynamic> json) {
    return BriefingEventModel(
      id: json['id'] as String,
      title: json['title'] as String,
      time: json['time'] as String?,
      icon: json['icon'] as String,
      description: json['description'] as String?,
      actionLabel: json['action_label'] as String?,
      eventType: json['event_type'] as String? ?? 'general',
      memberId: json['member_id'] as String?,
      memberName: json['member_name'] as String?,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'title': title,
      'time': time,
      'icon': icon,
      'description': description,
      'action_label': actionLabel,
      'event_type': eventType,
      'member_id': memberId,
      'member_name': memberName,
    };
  }

  BriefingEvent toEntity() {
    return BriefingEvent(
      id: id,
      title: title,
      time: time,
      icon: icon,
      description: description,
      actionLabel: actionLabel,
      eventType: eventType,
      memberId: memberId,
      memberName: memberName,
    );
  }
}

/// Model for BriefingAlert with JSON serialization.
class BriefingAlertModel extends BriefingAlert {
  const BriefingAlertModel({
    required super.id,
    required super.alertType,
    super.severity = 'warning',
    required super.title,
    required super.description,
    super.relatedEventIds = const [],
    super.actionLabel,
    super.icon = '⚠️',
  });

  factory BriefingAlertModel.fromJson(Map<String, dynamic> json) {
    final relatedIds = (json['related_event_ids'] as List<dynamic>?)
            ?.map((e) => e.toString())
            .toList() ??
        const [];
    return BriefingAlertModel(
      id: json['id'] as String,
      alertType: json['alert_type'] as String,
      severity: json['severity'] as String? ?? 'warning',
      title: json['title'] as String,
      description: json['description'] as String,
      relatedEventIds: relatedIds,
      actionLabel: json['action_label'] as String?,
      icon: json['icon'] as String? ?? '⚠️',
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'alert_type': alertType,
      'severity': severity,
      'title': title,
      'description': description,
      'related_event_ids': relatedEventIds,
      'action_label': actionLabel,
      'icon': icon,
    };
  }

  BriefingAlert toEntity() {
    return BriefingAlert(
      id: id,
      alertType: alertType,
      severity: severity,
      title: title,
      description: description,
      relatedEventIds: relatedEventIds,
      actionLabel: actionLabel,
      icon: icon,
    );
  }
}

/// Model for DailyBriefing with JSON serialization.
class DailyBriefingModel extends DailyBriefing {
  const DailyBriefingModel({
    required super.date,
    required super.greeting,
    required super.todayEventCount,
    required super.todayEvents,
    required super.preparationReminders,
    required super.weekRemainingCount,
    required super.smartSuggestions,
    super.alerts = const [],
  });

  factory DailyBriefingModel.fromJson(Map<String, dynamic> json) {
    final eventsJson = json['today_events'] as List<dynamic>? ?? [];
    final events = eventsJson
        .map((e) => BriefingEventModel.fromJson(e as Map<String, dynamic>))
        .toList();

    final remindersJson = json['preparation_reminders'] as List<dynamic>? ?? [];
    final reminders = remindersJson.map((e) => e as String).toList();

    final suggestionsJson = json['smart_suggestions'] as List<dynamic>? ?? [];
    final suggestions = suggestionsJson.map((e) {
      if (e is Map<String, dynamic>) {
        return BriefingSuggestion(
          label: e['label'] as String? ?? '',
          actionType: e['action_type'] as String? ?? 'open_chat',
          actionData: (e['action_data'] as Map<String, dynamic>?) ?? const {},
        );
      }
      // Backwards compat: plain string -> open_chat with prefill
      final label = e as String;
      return BriefingSuggestion(
        label: label,
        actionType: 'open_chat',
        actionData: {'prefill_text': label},
      );
    }).toList();

    // Parse alerts
    final alertsJson = json['alerts'] as List<dynamic>? ?? [];
    final alerts = alertsJson
        .map((e) => BriefingAlertModel.fromJson(e as Map<String, dynamic>))
        .toList();

    // Parse date string (YYYY-MM-DD format)
    DateTime date;
    final dateStr = json['date'] as String?;
    if (dateStr != null) {
      date = TimezoneUtils.parseApiTime(dateStr);
    } else {
      date = DateTime.now().toUtc();
    }

    return DailyBriefingModel(
      date: date,
      greeting: json['greeting'] as String? ?? '你好',
      todayEventCount: json['today_event_count'] as int? ?? 0,
      todayEvents: events,
      preparationReminders: reminders,
      weekRemainingCount: json['week_remaining_count'] as int? ?? 0,
      smartSuggestions: suggestions,
      alerts: alerts,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'date': TimezoneUtils.formatDateForApi(date),
      'greeting': greeting,
      'today_event_count': todayEventCount,
      'today_events': todayEvents
          .map((e) => (e as BriefingEventModel).toJson())
          .toList(),
      'preparation_reminders': preparationReminders,
      'week_remaining_count': weekRemainingCount,
      'smart_suggestions': smartSuggestions
          .map((s) => {
                'label': s.label,
                'action_type': s.actionType,
                'action_data': s.actionData,
              })
          .toList(),
      'alerts': alerts.map((e) => (e as BriefingAlertModel).toJson()).toList(),
    };
  }

  DailyBriefing toEntity() {
    return DailyBriefing(
      date: date,
      greeting: greeting,
      todayEventCount: todayEventCount,
      todayEvents: todayEvents
          .map((e) => (e as BriefingEventModel).toEntity())
          .toList(),
      preparationReminders: preparationReminders,
      weekRemainingCount: weekRemainingCount,
      smartSuggestions: smartSuggestions,
      alerts: alerts.map((e) => (e as BriefingAlertModel).toEntity()).toList(),
    );
  }
}

