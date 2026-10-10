import 'package:equatable/equatable.dart';

/// Connection status
enum ConnectionStatus {
  disconnected,
  connecting,
  connected,
  syncing,
  error,
  expired;

  String get displayName {
    switch (this) {
      case ConnectionStatus.disconnected:
        return '未连接';
      case ConnectionStatus.connecting:
        return '连接中';
      case ConnectionStatus.connected:
        return '已连接';
      case ConnectionStatus.syncing:
        return '同步中';
      case ConnectionStatus.error:
        return '错误';
      case ConnectionStatus.expired:
        return '已过期';
    }
  }

  bool get isActive => this == ConnectionStatus.connected || this == ConnectionStatus.syncing;
}

/// Sync frequency options
enum SyncFrequency {
  realtime,
  hourly,
  daily,
  weekly,
  manual;

  String get displayName {
    switch (this) {
      case SyncFrequency.realtime:
        return '实时';
      case SyncFrequency.hourly:
        return '每小时';
      case SyncFrequency.daily:
        return '每天';
      case SyncFrequency.weekly:
        return '每周';
      case SyncFrequency.manual:
        return '手动';
    }
  }
}

/// Usage permissions for connected data
class UsagePermissions extends Equatable {
  final bool dailyBriefing;
  final bool smartSuggestions;
  final bool memorySystem;
  final bool scheduleAggregation;

  const UsagePermissions({
    this.dailyBriefing = true,
    this.smartSuggestions = true,
    this.memorySystem = false,
    this.scheduleAggregation = true,
  });

  @override
  List<Object?> get props => [
        dailyBriefing,
        smartSuggestions,
        memorySystem,
        scheduleAggregation,
      ];

  UsagePermissions copyWith({
    bool? dailyBriefing,
    bool? smartSuggestions,
    bool? memorySystem,
    bool? scheduleAggregation,
  }) {
    return UsagePermissions(
      dailyBriefing: dailyBriefing ?? this.dailyBriefing,
      smartSuggestions: smartSuggestions ?? this.smartSuggestions,
      memorySystem: memorySystem ?? this.memorySystem,
      scheduleAggregation: scheduleAggregation ?? this.scheduleAggregation,
    );
  }

  Map<String, bool> toJson() => {
        'daily_briefing': dailyBriefing,
        'smart_suggestions': smartSuggestions,
        'memory_system': memorySystem,
        'schedule_aggregation': scheduleAggregation,
      };

  factory UsagePermissions.fromJson(Map<String, dynamic> json) {
    return UsagePermissions(
      dailyBriefing: json['daily_briefing'] as bool? ?? true,
      smartSuggestions: json['smart_suggestions'] as bool? ?? true,
      memorySystem: json['memory_system'] as bool? ?? false,
      scheduleAggregation: json['schedule_aggregation'] as bool? ?? true,
    );
  }
}

/// A data connection to an external service
class DataConnection extends Equatable {
  final String id;
  final String userId;
  final String? familyId;
  final String connectorId;
  final String connectorName;
  final ConnectionStatus status;
  final String? errorMessage;
  final List<String> grantedScopes;
  final SyncFrequency syncFrequency;
  final bool syncEnabled;
  final DateTime? lastSyncAt;
  final DateTime? nextSyncAt;
  final int syncErrorCount;
  final UsagePermissions usagePermissions;
  final DateTime? connectedAt;
  final DateTime createdAt;
  final DateTime updatedAt;

  const DataConnection({
    required this.id,
    required this.userId,
    this.familyId,
    required this.connectorId,
    required this.connectorName,
    required this.status,
    this.errorMessage,
    required this.grantedScopes,
    required this.syncFrequency,
    required this.syncEnabled,
    this.lastSyncAt,
    this.nextSyncAt,
    required this.syncErrorCount,
    required this.usagePermissions,
    this.connectedAt,
    required this.createdAt,
    required this.updatedAt,
  });

  @override
  List<Object?> get props => [
        id,
        userId,
        familyId,
        connectorId,
        connectorName,
        status,
        errorMessage,
        grantedScopes,
        syncFrequency,
        syncEnabled,
        lastSyncAt,
        nextSyncAt,
        syncErrorCount,
        usagePermissions,
        connectedAt,
        createdAt,
        updatedAt,
      ];

  bool get isConnected => status.isActive;
  bool get hasError => status == ConnectionStatus.error || errorMessage != null;
}
