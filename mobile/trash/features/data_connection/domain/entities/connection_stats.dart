import 'package:equatable/equatable.dart';

/// Statistics for a data connection
class ConnectionStats extends Equatable {
  final String connectionId;
  final String connectorId;
  final String status;
  final DateTime? lastSyncAt;
  final DateTime? nextSyncAt;
  final int syncErrorCount;
  final Map<String, int> usageByType;
  final int sinceDays;

  const ConnectionStats({
    required this.connectionId,
    required this.connectorId,
    required this.status,
    this.lastSyncAt,
    this.nextSyncAt,
    required this.syncErrorCount,
    required this.usageByType,
    required this.sinceDays,
  });

  @override
  List<Object?> get props => [
        connectionId,
        connectorId,
        status,
        lastSyncAt,
        nextSyncAt,
        syncErrorCount,
        usageByType,
        sinceDays,
      ];

  int get totalUsage => usageByType.values.fold(0, (a, b) => a + b);
}

/// Sync result from a manual or scheduled sync
class SyncResult extends Equatable {
  final bool success;
  final int recordsSynced;
  final int recordsUpdated;
  final int recordsDeleted;
  final int recordsFailed;
  final String? errorMessage;
  final String? errorCode;
  final DateTime? nextSyncAt;
  final List<String> warnings;

  const SyncResult({
    required this.success,
    required this.recordsSynced,
    required this.recordsUpdated,
    required this.recordsDeleted,
    required this.recordsFailed,
    this.errorMessage,
    this.errorCode,
    this.nextSyncAt,
    required this.warnings,
  });

  @override
  List<Object?> get props => [
        success,
        recordsSynced,
        recordsUpdated,
        recordsDeleted,
        recordsFailed,
        errorMessage,
        errorCode,
        nextSyncAt,
        warnings,
      ];

  int get totalRecords => recordsSynced + recordsUpdated + recordsDeleted;
}

/// Aggregated usage statistics across all connections
class ConnectionUsageSummary extends Equatable {
  final int calendarEventsSynced;
  final int emailsParsed;
  final int ordersParsed;
  final int suggestionsGenerated;
  final DateTime periodStart;
  final DateTime periodEnd;

  const ConnectionUsageSummary({
    required this.calendarEventsSynced,
    required this.emailsParsed,
    required this.ordersParsed,
    required this.suggestionsGenerated,
    required this.periodStart,
    required this.periodEnd,
  });

  @override
  List<Object?> get props => [
        calendarEventsSynced,
        emailsParsed,
        ordersParsed,
        suggestionsGenerated,
        periodStart,
        periodEnd,
      ];

  factory ConnectionUsageSummary.empty() {
    final now = DateTime.now();
    return ConnectionUsageSummary(
      calendarEventsSynced: 0,
      emailsParsed: 0,
      ordersParsed: 0,
      suggestionsGenerated: 0,
      periodStart: now.subtract(const Duration(days: 30)),
      periodEnd: now,
    );
  }
}
