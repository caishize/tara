import 'package:equatable/equatable.dart';

/// Summary statistics for the work report
class WorkReportSummary extends Equatable {
  final int totalCurationRuns;
  final int successfulCurationRuns;
  final int failedCurationRuns;
  final int totalEventsCurated;
  final int totalAssociationsCreated;
  final int totalHygieneRuns;
  final int totalHygieneActions;

  const WorkReportSummary({
    required this.totalCurationRuns,
    required this.successfulCurationRuns,
    required this.failedCurationRuns,
    required this.totalEventsCurated,
    required this.totalAssociationsCreated,
    required this.totalHygieneRuns,
    required this.totalHygieneActions,
  });

  @override
  List<Object?> get props => [
        totalCurationRuns,
        successfulCurationRuns,
        failedCurationRuns,
        totalEventsCurated,
        totalAssociationsCreated,
        totalHygieneRuns,
        totalHygieneActions,
      ];
}

/// A curation job summary item
class CurationJobSummary extends Equatable {
  final String jobId;
  final String status;
  final String triggerType;
  final String? dateRangeStart;
  final String? dateRangeEnd;
  final int eventsProcessed;
  final int eventsCurated;
  final int associationsCreated;
  final DateTime? startedAt;
  final DateTime? completedAt;
  final double? durationSeconds;
  final String? errorMessage;

  const CurationJobSummary({
    required this.jobId,
    required this.status,
    required this.triggerType,
    this.dateRangeStart,
    this.dateRangeEnd,
    required this.eventsProcessed,
    required this.eventsCurated,
    required this.associationsCreated,
    this.startedAt,
    this.completedAt,
    this.durationSeconds,
    this.errorMessage,
  });

  bool get isSuccess => status == 'completed';
  bool get isFailed => status == 'failed';
  bool get isRunning => status == 'running';

  String get statusText {
    switch (status) {
      case 'completed':
        return '成功';
      case 'failed':
        return '失败';
      case 'running':
        return '运行中';
      case 'pending':
        return '等待中';
      default:
        return status;
    }
  }

  String get triggerTypeText {
    switch (triggerType) {
      case 'scheduled':
        return '定时';
      case 'event':
        return '事件触发';
      case 'manual':
        return '手动';
      default:
        return triggerType;
    }
  }

  String get durationText {
    if (durationSeconds == null) return '';
    if (durationSeconds! < 60) return '${durationSeconds!.toStringAsFixed(1)}秒';
    return '${(durationSeconds! / 60).toStringAsFixed(1)}分钟';
  }

  @override
  List<Object?> get props => [jobId, status, triggerType, eventsProcessed];
}

/// A curated event within a job detail
class CuratedEventDetail extends Equatable {
  final String id;
  final String title;
  final String? eventType;
  final List<String> sourceTypes;
  final int mergedCount;
  final String? dedupReason;
  final DateTime? startTime;
  final DateTime? endTime;
  final String status;

  const CuratedEventDetail({
    required this.id,
    required this.title,
    this.eventType,
    required this.sourceTypes,
    required this.mergedCount,
    this.dedupReason,
    this.startTime,
    this.endTime,
    required this.status,
  });

  String get eventTypeText {
    switch (eventType) {
      case 'business_trip':
        return '出差';
      case 'travel':
        return '旅行';
      case 'meeting':
        return '会议';
      case 'appointment':
        return '约会';
      case 'reminder':
        return '提醒';
      default:
        return eventType ?? '其他';
    }
  }

  @override
  List<Object?> get props => [id, title, eventType];
}

/// An association within a job detail
class AssociationDetail extends Equatable {
  final String id;
  final String title;
  final String associationType;
  final String targetType;
  final String reason;
  final String priority;
  final double confidence;

  const AssociationDetail({
    required this.id,
    required this.title,
    required this.associationType,
    required this.targetType,
    required this.reason,
    required this.priority,
    required this.confidence,
  });

  String get associationTypeText {
    switch (associationType) {
      case 'location':
        return '地点关联';
      case 'temporal':
        return '时间关联';
      case 'person':
        return '人物关联';
      case 'semantic':
        return '语义关联';
      case 'memory':
        return '记忆关联';
      case 'task':
        return '任务关联';
      default:
        return associationType;
    }
  }

  @override
  List<Object?> get props => [id, title, associationType];
}

/// Detailed curation job with events and associations
class CurationJobDetail extends Equatable {
  final CurationJobSummary job;
  final List<CuratedEventDetail> curatedEvents;
  final List<AssociationDetail> associations;

  const CurationJobDetail({
    required this.job,
    required this.curatedEvents,
    required this.associations,
  });

  @override
  List<Object?> get props => [job, curatedEvents, associations];
}

/// A hygiene run log entry
class HygieneRunLog extends Equatable {
  final String id;
  final String familyId;
  final int inactiveDeleted;
  final int cancelledDeleted;
  final int dismissedDeleted;
  final int autoCompleted;
  final int jobsPurged;
  final int totalActions;
  final String status;
  final String? errorMessage;
  final DateTime? startedAt;
  final DateTime? completedAt;
  final double? durationSeconds;
  final DateTime? createdAt;

  const HygieneRunLog({
    required this.id,
    required this.familyId,
    required this.inactiveDeleted,
    required this.cancelledDeleted,
    required this.dismissedDeleted,
    required this.autoCompleted,
    required this.jobsPurged,
    required this.totalActions,
    required this.status,
    this.errorMessage,
    this.startedAt,
    this.completedAt,
    this.durationSeconds,
    this.createdAt,
  });

  bool get isSuccess => status == 'completed';

  String get summaryText {
    final parts = <String>[];
    if (inactiveDeleted > 0) parts.add('清理$inactiveDeleted个过期行程');
    if (cancelledDeleted > 0) parts.add('删除$cancelledDeleted个已取消行程');
    if (dismissedDeleted > 0) parts.add('清除$dismissedDeleted个忽略关联');
    if (autoCompleted > 0) parts.add('自动完成$autoCompleted个行程');
    if (jobsPurged > 0) parts.add('清理$jobsPurged条旧记录');
    if (parts.isEmpty) return '无清理操作';
    return parts.join('，');
  }

  @override
  List<Object?> get props => [id, totalActions, status];
}

/// Top-level work report
class WorkReport extends Equatable {
  final WorkReportSummary summary;
  final List<CurationJobSummary> curationJobs;
  final List<HygieneRunLog> hygieneLogs;

  const WorkReport({
    required this.summary,
    required this.curationJobs,
    required this.hygieneLogs,
  });

  factory WorkReport.empty() => const WorkReport(
        summary: WorkReportSummary(
          totalCurationRuns: 0,
          successfulCurationRuns: 0,
          failedCurationRuns: 0,
          totalEventsCurated: 0,
          totalAssociationsCreated: 0,
          totalHygieneRuns: 0,
          totalHygieneActions: 0,
        ),
        curationJobs: [],
        hygieneLogs: [],
      );

  @override
  List<Object?> get props => [summary, curationJobs, hygieneLogs];
}
