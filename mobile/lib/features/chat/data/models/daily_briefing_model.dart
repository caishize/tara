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

/// Model for DayTheme with JSON serialization.
class DayThemeModel extends DayTheme {
  const DayThemeModel({
    required super.title,
    super.primaryEventId,
    required super.focus,
    super.prepNote,
    super.eveningForward,
  });

  factory DayThemeModel.fromJson(Map<String, dynamic> json) {
    return DayThemeModel(
      title: json['title'] as String,
      primaryEventId: json['primary_event_id'] as String?,
      focus: json['focus'] as String,
      prepNote: json['prep_note'] as String?,
      eveningForward: json['evening_forward'] as String?,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'title': title,
      'primary_event_id': primaryEventId,
      'focus': focus,
      'prep_note': prepNote,
      'evening_forward': eveningForward,
    };
  }

  DayTheme toEntity() {
    return DayTheme(
      title: title,
      primaryEventId: primaryEventId,
      focus: focus,
      prepNote: prepNote,
      eveningForward: eveningForward,
    );
  }
}

/// Model for SecretaryAnnotation with JSON serialization.
class SecretaryAnnotationModel extends SecretaryAnnotation {
  const SecretaryAnnotationModel({
    required super.eventId,
    required super.text,
    required super.source,
  });

  factory SecretaryAnnotationModel.fromJson(Map<String, dynamic> json) {
    return SecretaryAnnotationModel(
      eventId: json['event_id'] as String,
      text: json['text'] as String,
      source: json['source'] as String? ?? 'context_enricher',
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'event_id': eventId,
      'text': text,
      'source': source,
    };
  }

  SecretaryAnnotation toEntity() {
    return SecretaryAnnotation(
      eventId: eventId,
      text: text,
      source: source,
    );
  }
}

/// Model for BriefingInsight with JSON serialization.
class BriefingInsightModel extends BriefingInsight {
  const BriefingInsightModel({
    required super.id,
    required super.insightType,
    required super.title,
    required super.content,
    super.priority = 5,
    super.urgency = 'normal',
    super.actionOptions = const [],
    super.actionData = const {},
  });

  factory BriefingInsightModel.fromJson(Map<String, dynamic> json) {
    return BriefingInsightModel(
      id: json['id'] as String,
      insightType: json['insight_type'] as String? ?? 'general',
      title: json['title'] as String,
      content: json['content'] as String,
      priority: json['priority'] as int? ?? 5,
      urgency: json['urgency'] as String? ?? 'normal',
      actionOptions: (json['action_options'] as List<dynamic>?)
              ?.map((e) => e as String)
              .toList() ??
          const [],
      actionData:
          (json['action_data'] as Map<String, dynamic>?) ?? const {},
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'insight_type': insightType,
      'title': title,
      'content': content,
      'priority': priority,
      'urgency': urgency,
      'action_options': actionOptions,
      'action_data': actionData,
    };
  }

  BriefingInsight toEntity() {
    return BriefingInsight(
      id: id,
      insightType: insightType,
      title: title,
      content: content,
      priority: priority,
      urgency: urgency,
      actionOptions: actionOptions,
      actionData: actionData,
    );
  }
}

/// Model for TimeSlot with JSON serialization.
class TimeSlotModel extends TimeSlot {
  const TimeSlotModel({
    required super.start,
    required super.end,
    super.eventId,
    required super.slotType,
    super.note,
  });

  factory TimeSlotModel.fromJson(Map<String, dynamic> json) {
    return TimeSlotModel(
      start: json['start'] as String,
      end: json['end'] as String,
      eventId: json['event_id'] as String?,
      slotType: json['slot_type'] as String? ?? 'free',
      note: json['note'] as String?,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'start': start,
      'end': end,
      'event_id': eventId,
      'slot_type': slotType,
      'note': note,
    };
  }

  TimeSlot toEntity() {
    return TimeSlot(
      start: start,
      end: end,
      eventId: eventId,
      slotType: slotType,
      note: note,
    );
  }
}

/// Model for HouseholdStatus with JSON serialization.
class HouseholdStatusModel extends HouseholdStatus {
  const HouseholdStatusModel({
    required super.id,
    required super.title,
    required super.description,
    required super.icon,
    super.urgency = 'normal',
    super.actionLabel,
  });

  factory HouseholdStatusModel.fromJson(Map<String, dynamic> json) {
    return HouseholdStatusModel(
      id: json['id'] as String,
      title: json['title'] as String,
      description: json['description'] as String,
      icon: json['icon'] as String? ?? '🏠',
      urgency: json['urgency'] as String? ?? 'normal',
      actionLabel: json['action_label'] as String?,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'title': title,
      'description': description,
      'icon': icon,
      'urgency': urgency,
      'action_label': actionLabel,
    };
  }

  HouseholdStatus toEntity() {
    return HouseholdStatus(
      id: id,
      title: title,
      description: description,
      icon: icon,
      urgency: urgency,
      actionLabel: actionLabel,
    );
  }
}

/// Model for UpcomingTrip with JSON serialization.
class UpcomingTripModel extends UpcomingTrip {
  const UpcomingTripModel({
    required super.tripId,
    super.tripName,
    required super.destination,
    required super.startDate,
    required super.endDate,
    super.tripType = 'leisure',
    super.status = 'planned',
  });

  factory UpcomingTripModel.fromJson(Map<String, dynamic> json) {
    return UpcomingTripModel(
      tripId: json['trip_id'] as String,
      tripName: json['trip_name'] as String?,
      destination: json['destination'] as String,
      startDate: TimezoneUtils.parseDate(json['start_date'] as String),
      endDate: TimezoneUtils.parseDate(json['end_date'] as String),
      tripType: json['trip_type'] as String? ?? 'leisure',
      status: json['status'] as String? ?? 'planning',
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'trip_id': tripId,
      'trip_name': tripName,
      'destination': destination,
      'start_date': TimezoneUtils.formatDateForApi(startDate),
      'end_date': TimezoneUtils.formatDateForApi(endDate),
      'trip_type': tripType,
      'status': status,
    };
  }

  UpcomingTrip toEntity() {
    return UpcomingTrip(
      tripId: tripId,
      tripName: tripName,
      destination: destination,
      startDate: startDate,
      endDate: endDate,
      tripType: tripType,
      status: status,
    );
  }
}

/// Model for DailyBriefing with JSON serialization.
class DailyBriefingModel extends DailyBriefing {
  const DailyBriefingModel({
    required super.date,
    required super.greeting,
    super.period = 'morning',
    required super.todayEventCount,
    required super.todayEvents,
    required super.preparationReminders,
    required super.weekRemainingCount,
    required super.smartSuggestions,
    super.alerts = const [],
    super.dayTheme,
    super.annotations = const [],
    super.secretarySummary,
    super.densityLevel = 'STANDARD',
    super.densityScore = 0.0,
    super.deferredCount = 0,
    super.suggestedReorder,
    super.insights = const [],
    super.householdStatus = const [],
    super.upcomingTrips = const [],
    super.tomorrowPreview = const [],
    super.timeSlots = const [],
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

    // Parse day theme
    final dayThemeJson = json['day_theme'] as Map<String, dynamic>?;
    final dayTheme =
        dayThemeJson != null ? DayThemeModel.fromJson(dayThemeJson) : null;

    // Parse annotations
    final annotationsJson = json['annotations'] as List<dynamic>? ?? [];
    final annotations = annotationsJson
        .map((e) =>
            SecretaryAnnotationModel.fromJson(e as Map<String, dynamic>))
        .toList();

    // Parse insights
    final insightsJson = json['insights'] as List<dynamic>? ?? [];
    final insights = insightsJson
        .map(
            (e) => BriefingInsightModel.fromJson(e as Map<String, dynamic>))
        .toList();

    // Parse time slots
    final timeSlotsJson = json['time_slots'] as List<dynamic>? ?? [];
    final timeSlots = timeSlotsJson
        .map((e) => TimeSlotModel.fromJson(e as Map<String, dynamic>))
        .toList();

    // Parse household status
    final householdJson = json['household_status'] as List<dynamic>? ?? [];
    final householdStatus = householdJson
        .map((e) =>
            HouseholdStatusModel.fromJson(e as Map<String, dynamic>))
        .toList();

    // Parse upcoming trips
    final tripsJson = json['upcoming_trips'] as List<dynamic>? ?? [];
    final upcomingTrips = tripsJson
        .map(
            (e) => UpcomingTripModel.fromJson(e as Map<String, dynamic>))
        .toList();

    // Parse tomorrow preview
    final tomorrowJson = json['tomorrow_preview'] as List<dynamic>? ?? [];
    final tomorrowPreview = tomorrowJson
        .map((e) => BriefingEventModel.fromJson(e as Map<String, dynamic>))
        .toList();

    // Parse suggested reorder
    final reorderJson = json['suggested_reorder'] as List<dynamic>?;
    final suggestedReorder =
        reorderJson?.map((e) => e as String).toList();

    return DailyBriefingModel(
      date: date,
      greeting: json['greeting'] as String? ?? '你好',
      period: json['period'] as String? ?? 'morning',
      todayEventCount: json['today_event_count'] as int? ?? 0,
      todayEvents: events,
      preparationReminders: reminders,
      weekRemainingCount: json['week_remaining_count'] as int? ?? 0,
      smartSuggestions: suggestions,
      alerts: alerts,
      dayTheme: dayTheme,
      annotations: annotations,
      secretarySummary: json['secretary_summary'] as String?,
      densityLevel: json['density_level'] as String? ?? 'STANDARD',
      densityScore: (json['density_score'] as num?)?.toDouble() ?? 0.0,
      deferredCount: json['deferred_count'] as int? ?? 0,
      suggestedReorder: suggestedReorder,
      insights: insights,
      householdStatus: householdStatus,
      upcomingTrips: upcomingTrips,
      tomorrowPreview: tomorrowPreview,
      timeSlots: timeSlots,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'date': TimezoneUtils.formatDateForApi(date),
      'greeting': greeting,
      'period': period,
      'today_event_count': todayEventCount,
      'today_events': todayEvents.map((e) => _eventToJson(e)).toList(),
      'preparation_reminders': preparationReminders,
      'week_remaining_count': weekRemainingCount,
      'smart_suggestions': smartSuggestions
          .map((s) => {
                'label': s.label,
                'action_type': s.actionType,
                'action_data': s.actionData,
              })
          .toList(),
      'alerts': alerts.map((e) => _alertToJson(e)).toList(),
      'day_theme': dayTheme != null ? _dayThemeToJson(dayTheme!) : null,
      'annotations': annotations.map((e) => _annotationToJson(e)).toList(),
      'secretary_summary': secretarySummary,
      'density_level': densityLevel,
      'density_score': densityScore,
      'deferred_count': deferredCount,
      'suggested_reorder': suggestedReorder,
      'insights': insights.map((e) => _insightToJson(e)).toList(),
      'household_status':
          householdStatus.map((e) => _householdToJson(e)).toList(),
      'upcoming_trips': upcomingTrips.map((e) => _tripToJson(e)).toList(),
      'tomorrow_preview': tomorrowPreview.map((e) => _eventToJson(e)).toList(),
      'time_slots': timeSlots.map((e) => _timeSlotToJson(e)).toList(),
    };
  }

  // Safe serialization helpers that work with both Model and Entity types.
  static Map<String, dynamic> _eventToJson(BriefingEvent e) {
    if (e is BriefingEventModel) return e.toJson();
    return {
      'id': e.id, 'title': e.title, 'time': e.time,
      'icon': e.icon, 'description': e.description,
      'action_label': e.actionLabel, 'event_type': e.eventType,
      'member_id': e.memberId, 'member_name': e.memberName,
    };
  }

  static Map<String, dynamic> _alertToJson(BriefingAlert e) {
    if (e is BriefingAlertModel) return e.toJson();
    return {
      'id': e.id, 'alert_type': e.alertType, 'severity': e.severity,
      'title': e.title, 'description': e.description,
      'related_event_ids': e.relatedEventIds,
      'action_label': e.actionLabel, 'icon': e.icon,
    };
  }

  static Map<String, dynamic> _dayThemeToJson(DayTheme e) {
    if (e is DayThemeModel) return e.toJson();
    return {
      'title': e.title, 'primary_event_id': e.primaryEventId,
      'focus': e.focus, 'prep_note': e.prepNote,
      'evening_forward': e.eveningForward,
    };
  }

  static Map<String, dynamic> _annotationToJson(SecretaryAnnotation e) {
    if (e is SecretaryAnnotationModel) return e.toJson();
    return {'event_id': e.eventId, 'text': e.text, 'source': e.source};
  }

  static Map<String, dynamic> _insightToJson(BriefingInsight e) {
    if (e is BriefingInsightModel) return e.toJson();
    return {
      'id': e.id, 'insight_type': e.insightType, 'title': e.title,
      'content': e.content, 'priority': e.priority, 'urgency': e.urgency,
      'action_options': e.actionOptions, 'action_data': e.actionData,
    };
  }

  static Map<String, dynamic> _householdToJson(HouseholdStatus e) {
    if (e is HouseholdStatusModel) return e.toJson();
    return {
      'id': e.id, 'title': e.title, 'description': e.description,
      'icon': e.icon, 'urgency': e.urgency, 'action_label': e.actionLabel,
    };
  }

  static Map<String, dynamic> _tripToJson(UpcomingTrip e) {
    if (e is UpcomingTripModel) return e.toJson();
    return {
      'trip_id': e.tripId, 'trip_name': e.tripName,
      'destination': e.destination,
      'start_date': TimezoneUtils.formatDateForApi(e.startDate),
      'end_date': TimezoneUtils.formatDateForApi(e.endDate),
      'trip_type': e.tripType, 'status': e.status,
    };
  }

  static Map<String, dynamic> _timeSlotToJson(TimeSlot e) {
    if (e is TimeSlotModel) return e.toJson();
    return {
      'start': e.start, 'end': e.end, 'event_id': e.eventId,
      'slot_type': e.slotType, 'note': e.note,
    };
  }

  DailyBriefing toEntity() {
    return DailyBriefing(
      date: date,
      greeting: greeting,
      period: period,
      todayEventCount: todayEventCount,
      todayEvents:
          todayEvents.map((e) => (e as BriefingEventModel).toEntity()).toList(),
      preparationReminders: preparationReminders,
      weekRemainingCount: weekRemainingCount,
      smartSuggestions: smartSuggestions,
      alerts: alerts.map((e) => (e as BriefingAlertModel).toEntity()).toList(),
      dayTheme: dayTheme != null
          ? (dayTheme as DayThemeModel).toEntity()
          : null,
      annotations: annotations
          .map((e) => (e as SecretaryAnnotationModel).toEntity())
          .toList(),
      secretarySummary: secretarySummary,
      densityLevel: densityLevel,
      densityScore: densityScore,
      deferredCount: deferredCount,
      suggestedReorder: suggestedReorder,
      insights: insights
          .map((e) => (e as BriefingInsightModel).toEntity())
          .toList(),
      householdStatus: householdStatus
          .map((e) => (e as HouseholdStatusModel).toEntity())
          .toList(),
      upcomingTrips: upcomingTrips
          .map((e) => (e as UpcomingTripModel).toEntity())
          .toList(),
      tomorrowPreview: tomorrowPreview
          .map((e) => (e as BriefingEventModel).toEntity())
          .toList(),
      timeSlots: timeSlots
          .map((e) => (e as TimeSlotModel).toEntity())
          .toList(),
    );
  }
}
