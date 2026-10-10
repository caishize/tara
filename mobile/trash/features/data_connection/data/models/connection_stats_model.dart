import '../../domain/entities/connection_stats.dart';

class ConnectionStatsModel extends ConnectionStats {
  const ConnectionStatsModel({
    required super.connectionId,
    required super.connectorId,
    required super.status,
    super.lastSyncAt,
    super.nextSyncAt,
    required super.syncErrorCount,
    required super.usageByType,
    required super.sinceDays,
  });

  factory ConnectionStatsModel.fromJson(Map<String, dynamic> json) {
    return ConnectionStatsModel(
      connectionId: json['connection_id'] as String,
      connectorId: json['connector_id'] as String,
      status: json['status'] as String,
      lastSyncAt: json['last_sync_at'] != null
          ? DateTime.parse(json['last_sync_at'] as String)
          : null,
      nextSyncAt: json['next_sync_at'] != null
          ? DateTime.parse(json['next_sync_at'] as String)
          : null,
      syncErrorCount: json['sync_error_count'] as int? ?? 0,
      usageByType: (json['usage_by_type'] as Map<String, dynamic>?)?.map(
            (k, v) => MapEntry(k, v as int),
          ) ??
          {},
      sinceDays: json['since_days'] as int? ?? 30,
    );
  }
}

class SyncResultModel extends SyncResult {
  const SyncResultModel({
    required super.success,
    required super.recordsSynced,
    required super.recordsUpdated,
    required super.recordsDeleted,
    required super.recordsFailed,
    super.errorMessage,
    super.errorCode,
    super.nextSyncAt,
    required super.warnings,
  });

  factory SyncResultModel.fromJson(Map<String, dynamic> json) {
    return SyncResultModel(
      success: json['success'] as bool? ?? false,
      recordsSynced: json['records_synced'] as int? ?? 0,
      recordsUpdated: json['records_updated'] as int? ?? 0,
      recordsDeleted: json['records_deleted'] as int? ?? 0,
      recordsFailed: json['records_failed'] as int? ?? 0,
      errorMessage: json['error_message'] as String?,
      errorCode: json['error_code'] as String?,
      nextSyncAt: json['next_sync_at'] != null
          ? DateTime.parse(json['next_sync_at'] as String)
          : null,
      warnings: (json['warnings'] as List<dynamic>?)
              ?.map((e) => e as String)
              .toList() ??
          [],
    );
  }
}

class ConnectionUsageSummaryModel extends ConnectionUsageSummary {
  const ConnectionUsageSummaryModel({
    required super.calendarEventsSynced,
    required super.emailsParsed,
    required super.ordersParsed,
    required super.suggestionsGenerated,
    required super.periodStart,
    required super.periodEnd,
  });

  factory ConnectionUsageSummaryModel.fromJson(Map<String, dynamic> json) {
    return ConnectionUsageSummaryModel(
      calendarEventsSynced: json['calendar_events_synced'] as int? ?? 0,
      emailsParsed: json['emails_parsed'] as int? ?? 0,
      ordersParsed: json['orders_parsed'] as int? ?? 0,
      suggestionsGenerated: json['suggestions_generated'] as int? ?? 0,
      periodStart: json['period_start'] != null
          ? DateTime.parse(json['period_start'] as String)
          : DateTime.now().subtract(const Duration(days: 30)),
      periodEnd: json['period_end'] != null
          ? DateTime.parse(json['period_end'] as String)
          : DateTime.now(),
    );
  }
}
