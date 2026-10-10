import '../../domain/entities/work_report.dart';

class WorkReportModel {
  static WorkReport fromJson(Map<String, dynamic> json) {
    final summaryJson = json['summary'] as Map<String, dynamic>? ?? {};
    final curationList = json['curation_jobs'] as List<dynamic>? ?? [];
    final hygieneList = json['hygiene_logs'] as List<dynamic>? ?? [];

    return WorkReport(
      summary: _parseSummary(summaryJson),
      curationJobs: curationList
          .map((j) => _parseCurationJob(j as Map<String, dynamic>))
          .toList(),
      hygieneLogs: hygieneList
          .map((l) => _parseHygieneLog(l as Map<String, dynamic>))
          .toList(),
    );
  }

  static WorkReportSummary _parseSummary(Map<String, dynamic> json) {
    return WorkReportSummary(
      totalCurationRuns: json['total_curation_runs'] as int? ?? 0,
      successfulCurationRuns: json['successful_curation_runs'] as int? ?? 0,
      failedCurationRuns: json['failed_curation_runs'] as int? ?? 0,
      totalEventsCurated: json['total_events_curated'] as int? ?? 0,
      totalAssociationsCreated:
          json['total_associations_created'] as int? ?? 0,
      totalHygieneRuns: json['total_hygiene_runs'] as int? ?? 0,
      totalHygieneActions: json['total_hygiene_actions'] as int? ?? 0,
    );
  }

  static CurationJobSummary _parseCurationJob(Map<String, dynamic> json) {
    return CurationJobSummary(
      jobId: json['job_id'] as String? ?? '',
      status: json['status'] as String? ?? 'pending',
      triggerType: json['trigger_type'] as String? ?? 'scheduled',
      dateRangeStart: json['date_range_start'] as String?,
      dateRangeEnd: json['date_range_end'] as String?,
      eventsProcessed: json['events_processed'] as int? ?? 0,
      eventsCurated: json['events_curated'] as int? ?? 0,
      associationsCreated: json['associations_created'] as int? ?? 0,
      startedAt: _parseDateTime(json['started_at']),
      completedAt: _parseDateTime(json['completed_at']),
      durationSeconds: (json['duration_seconds'] as num?)?.toDouble(),
      errorMessage: json['error_message'] as String?,
    );
  }

  static HygieneRunLog _parseHygieneLog(Map<String, dynamic> json) {
    return HygieneRunLog(
      id: json['id'] as String? ?? '',
      familyId: json['family_id'] as String? ?? '',
      inactiveDeleted: json['inactive_deleted'] as int? ?? 0,
      cancelledDeleted: json['cancelled_deleted'] as int? ?? 0,
      dismissedDeleted: json['dismissed_deleted'] as int? ?? 0,
      autoCompleted: json['auto_completed'] as int? ?? 0,
      jobsPurged: json['jobs_purged'] as int? ?? 0,
      totalActions: json['total_actions'] as int? ?? 0,
      status: json['status'] as String? ?? 'completed',
      errorMessage: json['error_message'] as String?,
      startedAt: _parseDateTime(json['started_at']),
      completedAt: _parseDateTime(json['completed_at']),
      durationSeconds: (json['duration_seconds'] as num?)?.toDouble(),
      createdAt: _parseDateTime(json['created_at']),
    );
  }

  static DateTime? _parseDateTime(dynamic value) {
    if (value == null) return null;
    if (value is String) return DateTime.tryParse(value)?.toLocal();
    return null;
  }
}

class CurationJobDetailModel {
  static CurationJobDetail fromJson(Map<String, dynamic> json) {
    final jobJson = json['job'] as Map<String, dynamic>? ?? {};
    final eventsList = json['curated_events'] as List<dynamic>? ?? [];
    final assocsList = json['associations'] as List<dynamic>? ?? [];

    return CurationJobDetail(
      job: WorkReportModel._parseCurationJob(jobJson),
      curatedEvents: eventsList
          .map((e) => _parseCuratedEvent(e as Map<String, dynamic>))
          .toList(),
      associations: assocsList
          .map((a) => _parseAssociation(a as Map<String, dynamic>))
          .toList(),
    );
  }

  static CuratedEventDetail _parseCuratedEvent(Map<String, dynamic> json) {
    return CuratedEventDetail(
      id: json['id'] as String? ?? '',
      title: json['title'] as String? ?? '',
      eventType: json['event_type'] as String?,
      sourceTypes: (json['source_types'] as List<dynamic>?)
              ?.map((e) => e as String)
              .toList() ??
          [],
      mergedCount: json['merged_count'] as int? ?? 1,
      dedupReason: json['dedup_reason'] as String?,
      startTime: WorkReportModel._parseDateTime(json['start_time']),
      endTime: WorkReportModel._parseDateTime(json['end_time']),
      status: json['status'] as String? ?? 'pending',
    );
  }

  static AssociationDetail _parseAssociation(Map<String, dynamic> json) {
    return AssociationDetail(
      id: json['id'] as String? ?? '',
      title: json['title'] as String? ?? '',
      associationType: json['association_type'] as String? ?? '',
      targetType: json['target_type'] as String? ?? '',
      reason: json['reason'] as String? ?? '',
      priority: json['priority'] as String? ?? 'convenient',
      confidence: (json['confidence'] as num?)?.toDouble() ?? 0.8,
    );
  }
}
