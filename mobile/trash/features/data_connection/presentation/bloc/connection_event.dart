import 'package:equatable/equatable.dart';

import '../../domain/entities/connector_metadata.dart';
import '../../domain/entities/data_connection.dart';

/// Base event class for data connections
abstract class ConnectionEvent extends Equatable {
  const ConnectionEvent();

  @override
  List<Object?> get props => [];
}

/// Load available connectors
class LoadConnectors extends ConnectionEvent {
  final DataCategory? category;
  final String region;

  const LoadConnectors({
    this.category,
    this.region = 'CN',
  });

  @override
  List<Object?> get props => [category, region];
}

/// Load user connections
class LoadConnections extends ConnectionEvent {
  final bool includeDisconnected;

  const LoadConnections({
    this.includeDisconnected = false,
  });

  @override
  List<Object?> get props => [includeDisconnected];
}

/// Refresh all data
class RefreshConnectionData extends ConnectionEvent {
  const RefreshConnectionData();
}

/// Initiate a new connection
class InitiateConnection extends ConnectionEvent {
  final String connectorId;
  final List<String>? scopes;

  const InitiateConnection({
    required this.connectorId,
    this.scopes,
  });

  @override
  List<Object?> get props => [connectorId, scopes];
}

/// Complete OAuth connection
class CompleteConnection extends ConnectionEvent {
  final String connectionId;
  final String code;
  final String? state;

  const CompleteConnection({
    required this.connectionId,
    required this.code,
    this.state,
  });

  @override
  List<Object?> get props => [connectionId, code, state];
}

/// Disconnect a connection
class DisconnectConnection extends ConnectionEvent {
  final String connectionId;

  const DisconnectConnection(this.connectionId);

  @override
  List<Object?> get props => [connectionId];
}

/// Update connection settings
class UpdateConnectionSettings extends ConnectionEvent {
  final String connectionId;
  final SyncFrequency? syncFrequency;
  final bool? syncEnabled;
  final UsagePermissions? usagePermissions;

  const UpdateConnectionSettings({
    required this.connectionId,
    this.syncFrequency,
    this.syncEnabled,
    this.usagePermissions,
  });

  @override
  List<Object?> get props => [connectionId, syncFrequency, syncEnabled, usagePermissions];
}

/// Trigger manual sync
class TriggerSync extends ConnectionEvent {
  final String connectionId;
  final bool fullSync;

  const TriggerSync({
    required this.connectionId,
    this.fullSync = false,
  });

  @override
  List<Object?> get props => [connectionId, fullSync];
}

/// Load connection statistics
class LoadConnectionStats extends ConnectionEvent {
  final String connectionId;
  final int sinceDays;

  const LoadConnectionStats({
    required this.connectionId,
    this.sinceDays = 30,
  });

  @override
  List<Object?> get props => [connectionId, sinceDays];
}

/// Load usage summary
class LoadUsageSummary extends ConnectionEvent {
  const LoadUsageSummary();
}
