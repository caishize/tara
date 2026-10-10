import 'package:equatable/equatable.dart';

class ReportSummary extends Equatable {
  final String range;
  final int totalActions;
  final int eventsManaged;
  final int memoriesExtracted;
  final int insightsGenerated;
  final int remindersSent;
  final int briefingsRun;
  final int giftsTracked;
  final double vsLastPeriod;

  const ReportSummary({
    required this.range,
    required this.totalActions,
    required this.eventsManaged,
    required this.memoriesExtracted,
    required this.insightsGenerated,
    required this.remindersSent,
    required this.briefingsRun,
    required this.giftsTracked,
    required this.vsLastPeriod,
  });

  factory ReportSummary.empty() => const ReportSummary(
        range: 'week',
        totalActions: 0,
        eventsManaged: 0,
        memoriesExtracted: 0,
        insightsGenerated: 0,
        remindersSent: 0,
        briefingsRun: 0,
        giftsTracked: 0,
        vsLastPeriod: 0.0,
      );

  factory ReportSummary.fromJson(Map<String, dynamic> json) {
    final breakdown =
        json['breakdown'] as Map<String, dynamic>? ?? <String, dynamic>{};
    final comparison =
        json['comparison'] as Map<String, dynamic>? ?? <String, dynamic>{};
    return ReportSummary(
      range: json['range'] as String? ?? 'week',
      totalActions: (json['total_actions'] as num?)?.toInt() ?? 0,
      eventsManaged: (breakdown['events_managed'] as num?)?.toInt() ?? 0,
      memoriesExtracted:
          (breakdown['memories_extracted'] as num?)?.toInt() ?? 0,
      insightsGenerated:
          (breakdown['insights_generated'] as num?)?.toInt() ?? 0,
      remindersSent: (breakdown['reminders_sent'] as num?)?.toInt() ?? 0,
      briefingsRun: (breakdown['briefings_run'] as num?)?.toInt() ?? 0,
      giftsTracked: (breakdown['gifts_tracked'] as num?)?.toInt() ?? 0,
      vsLastPeriod: (comparison['vs_last_period'] as num?)?.toDouble() ?? 0.0,
    );
  }

  @override
  List<Object?> get props => [
        range,
        totalActions,
        eventsManaged,
        memoriesExtracted,
        insightsGenerated,
        remindersSent,
        briefingsRun,
        giftsTracked,
        vsLastPeriod,
      ];
}

class ReportTimelineItem extends Equatable {
  final String timestamp;
  final String actionType;
  final String description;
  final String status;

  const ReportTimelineItem({
    required this.timestamp,
    required this.actionType,
    required this.description,
    required this.status,
  });

  factory ReportTimelineItem.fromJson(Map<String, dynamic> json) {
    return ReportTimelineItem(
      timestamp: json['timestamp'] as String? ?? '',
      actionType: json['action_type'] as String? ?? '',
      description: json['description'] as String? ?? '',
      status: json['status'] as String? ?? 'unknown',
    );
  }

  DateTime? get dateTime {
    if (timestamp.isEmpty) return null;
    return DateTime.tryParse(timestamp)?.toLocal();
  }

  @override
  List<Object?> get props => [timestamp, actionType, description, status];
}

class SecretaryReport extends Equatable {
  final ReportSummary summary;
  final List<ReportTimelineItem> timeline;

  const SecretaryReport({
    required this.summary,
    required this.timeline,
  });

  factory SecretaryReport.empty() => SecretaryReport(
        summary: ReportSummary.empty(),
        timeline: const [],
      );

  @override
  List<Object?> get props => [summary, timeline];
}
