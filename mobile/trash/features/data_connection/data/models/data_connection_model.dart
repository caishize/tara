import '../../domain/entities/data_connection.dart';

class DataConnectionModel extends DataConnection {
  const DataConnectionModel({
    required super.id,
    required super.userId,
    super.familyId,
    required super.connectorId,
    required super.connectorName,
    required super.status,
    super.errorMessage,
    required super.grantedScopes,
    required super.syncFrequency,
    required super.syncEnabled,
    super.lastSyncAt,
    super.nextSyncAt,
    required super.syncErrorCount,
    required super.usagePermissions,
    super.connectedAt,
    required super.createdAt,
    required super.updatedAt,
  });

  factory DataConnectionModel.fromJson(Map<String, dynamic> json) {
    return DataConnectionModel(
      id: json['id'] as String,
      userId: json['user_id'] as String,
      familyId: json['family_id'] as String?,
      connectorId: json['connector_id'] as String,
      connectorName: json['connector_name'] as String,
      status: _parseStatus(json['status'] as String?),
      errorMessage: json['error_message'] as String?,
      grantedScopes: (json['granted_scopes'] as List<dynamic>?)
              ?.map((e) => e as String)
              .toList() ??
          [],
      syncFrequency: _parseSyncFrequency(json['sync_frequency'] as String?),
      syncEnabled: json['sync_enabled'] as bool? ?? true,
      lastSyncAt: json['last_sync_at'] != null
          ? DateTime.parse(json['last_sync_at'] as String)
          : null,
      nextSyncAt: json['next_sync_at'] != null
          ? DateTime.parse(json['next_sync_at'] as String)
          : null,
      syncErrorCount: json['sync_error_count'] as int? ?? 0,
      usagePermissions: json['usage_permissions'] != null
          ? UsagePermissions.fromJson(json['usage_permissions'] as Map<String, dynamic>)
          : const UsagePermissions(),
      connectedAt: json['connected_at'] != null
          ? DateTime.parse(json['connected_at'] as String)
          : null,
      createdAt: DateTime.parse(json['created_at'] as String),
      updatedAt: DateTime.parse(json['updated_at'] as String),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'user_id': userId,
      'family_id': familyId,
      'connector_id': connectorId,
      'connector_name': connectorName,
      'status': status.name,
      'error_message': errorMessage,
      'granted_scopes': grantedScopes,
      'sync_frequency': syncFrequency.name,
      'sync_enabled': syncEnabled,
      'last_sync_at': lastSyncAt?.toIso8601String(),
      'next_sync_at': nextSyncAt?.toIso8601String(),
      'sync_error_count': syncErrorCount,
      'usage_permissions': usagePermissions.toJson(),
      'connected_at': connectedAt?.toIso8601String(),
      'created_at': createdAt.toIso8601String(),
      'updated_at': updatedAt.toIso8601String(),
    };
  }

  static ConnectionStatus _parseStatus(String? value) {
    if (value == null) return ConnectionStatus.disconnected;
    return ConnectionStatus.values.firstWhere(
      (e) => e.name == value.toLowerCase(),
      orElse: () => ConnectionStatus.disconnected,
    );
  }

  static SyncFrequency _parseSyncFrequency(String? value) {
    if (value == null) return SyncFrequency.daily;
    return SyncFrequency.values.firstWhere(
      (e) => e.name == value.toLowerCase(),
      orElse: () => SyncFrequency.daily,
    );
  }
}
