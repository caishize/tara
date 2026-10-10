import 'package:equatable/equatable.dart';

/// User configurable settings for insight generation cycles.
///
/// Controls various thresholds and time windows used by the
/// proactive insight service.
class InsightSettings extends Equatable {
  /// Number of days to analyze for emotion patterns (1-30, default: 7)
  final int emotionPatternWindowDays;

  /// Days without contact before reminder is generated (7-365, default: 90)
  final int relationshipReminderThresholdDays;

  /// Number of days before an insight expires (1-30, default: 7)
  final int insightExpiryDays;

  /// Days for a plan to be considered old and need follow-up (1-60, default: 14)
  final int oldPlanFollowupThresholdDays;

  /// Days ahead to check for upcoming trips (1-30, default: 7)
  final int upcomingTripCheckDays;

  /// Hour of day to run timeline curation (0-23, default: 2 = 2:00 AM)
  final int curationScheduleHour;

  /// Days ahead to curate in timeline (1-30, default: 14)
  final int curationDaysAhead;

  /// Whether to auto-curate when travel plan is created (default: true)
  final bool autoCurateOnTravelCreate;

  /// Minimum interval between curation runs in minutes (15-1440, default: 60)
  final int curationIntervalMinutes;

  /// Whether to auto-curate when events are created/updated/deleted (default: true)
  final bool autoCurateOnEventChange;

  const InsightSettings({
    this.emotionPatternWindowDays = 7,
    this.relationshipReminderThresholdDays = 90,
    this.insightExpiryDays = 7,
    this.oldPlanFollowupThresholdDays = 14,
    this.upcomingTripCheckDays = 7,
    this.curationScheduleHour = 2,
    this.curationDaysAhead = 14,
    this.autoCurateOnTravelCreate = true,
    this.curationIntervalMinutes = 60,
    this.autoCurateOnEventChange = true,
  });

  /// Default settings
  static const InsightSettings defaults = InsightSettings();

  /// Valid ranges for each setting
  static const Map<String, (int, int)> ranges = {
    'emotionPatternWindowDays': (1, 30),
    'relationshipReminderThresholdDays': (7, 365),
    'insightExpiryDays': (1, 30),
    'oldPlanFollowupThresholdDays': (1, 60),
    'upcomingTripCheckDays': (1, 30),
    'curationScheduleHour': (0, 23),
    'curationDaysAhead': (1, 30),
    'curationIntervalMinutes': (15, 1440),
  };

  InsightSettings copyWith({
    int? emotionPatternWindowDays,
    int? relationshipReminderThresholdDays,
    int? insightExpiryDays,
    int? oldPlanFollowupThresholdDays,
    int? upcomingTripCheckDays,
    int? curationScheduleHour,
    int? curationDaysAhead,
    bool? autoCurateOnTravelCreate,
    int? curationIntervalMinutes,
    bool? autoCurateOnEventChange,
  }) {
    return InsightSettings(
      emotionPatternWindowDays:
          emotionPatternWindowDays ?? this.emotionPatternWindowDays,
      relationshipReminderThresholdDays:
          relationshipReminderThresholdDays ?? this.relationshipReminderThresholdDays,
      insightExpiryDays: insightExpiryDays ?? this.insightExpiryDays,
      oldPlanFollowupThresholdDays:
          oldPlanFollowupThresholdDays ?? this.oldPlanFollowupThresholdDays,
      upcomingTripCheckDays:
          upcomingTripCheckDays ?? this.upcomingTripCheckDays,
      curationScheduleHour:
          curationScheduleHour ?? this.curationScheduleHour,
      curationDaysAhead:
          curationDaysAhead ?? this.curationDaysAhead,
      autoCurateOnTravelCreate:
          autoCurateOnTravelCreate ?? this.autoCurateOnTravelCreate,
      curationIntervalMinutes:
          curationIntervalMinutes ?? this.curationIntervalMinutes,
      autoCurateOnEventChange:
          autoCurateOnEventChange ?? this.autoCurateOnEventChange,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'emotion_pattern_window_days': emotionPatternWindowDays,
      'relationship_reminder_threshold_days': relationshipReminderThresholdDays,
      'insight_expiry_days': insightExpiryDays,
      'old_plan_followup_threshold_days': oldPlanFollowupThresholdDays,
      'upcoming_trip_check_days': upcomingTripCheckDays,
      'curation_schedule_hour': curationScheduleHour,
      'curation_days_ahead': curationDaysAhead,
      'auto_curate_on_travel_create': autoCurateOnTravelCreate,
      'curation_interval_minutes': curationIntervalMinutes,
      'auto_curate_on_event_change': autoCurateOnEventChange,
    };
  }

  factory InsightSettings.fromJson(Map<String, dynamic> json) {
    return InsightSettings(
      emotionPatternWindowDays: json['emotion_pattern_window_days'] as int? ?? 7,
      relationshipReminderThresholdDays:
          json['relationship_reminder_threshold_days'] as int? ?? 90,
      insightExpiryDays: json['insight_expiry_days'] as int? ?? 7,
      oldPlanFollowupThresholdDays:
          json['old_plan_followup_threshold_days'] as int? ?? 14,
      upcomingTripCheckDays: json['upcoming_trip_check_days'] as int? ?? 7,
      curationScheduleHour: json['curation_schedule_hour'] as int? ?? 2,
      curationDaysAhead: json['curation_days_ahead'] as int? ?? 14,
      autoCurateOnTravelCreate:
          json['auto_curate_on_travel_create'] as bool? ?? true,
      curationIntervalMinutes:
          json['curation_interval_minutes'] as int? ?? 60,
      autoCurateOnEventChange:
          json['auto_curate_on_event_change'] as bool? ?? true,
    );
  }

  @override
  List<Object?> get props => [
        emotionPatternWindowDays,
        relationshipReminderThresholdDays,
        insightExpiryDays,
        oldPlanFollowupThresholdDays,
        upcomingTripCheckDays,
        curationScheduleHour,
        curationDaysAhead,
        autoCurateOnTravelCreate,
        curationIntervalMinutes,
        autoCurateOnEventChange,
      ];
}
