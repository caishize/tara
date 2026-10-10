import 'package:equatable/equatable.dart';

import '../../data/models/connector_metadata_model.dart';
import '../../data/models/data_connection_model.dart';
import '../../domain/entities/connector_metadata.dart';
import '../../domain/entities/data_connection.dart';
import '../../domain/entities/connection_stats.dart';

/// Base state class for data connections
abstract class DataConnectionState extends Equatable {
  const DataConnectionState();

  @override
  List<Object?> get props => [];
}

/// Initial state
class ConnectionInitial extends DataConnectionState {
  const ConnectionInitial();
}

/// Loading state
class ConnectionLoading extends DataConnectionState {
  const ConnectionLoading();
}

/// Loaded state with all data
class ConnectionLoaded extends DataConnectionState {
  final List<ConnectorMetadataModel> connectors;
  final List<DataConnectionModel> connections;
  final ConnectionUsageSummary? usageSummary;

  const ConnectionLoaded({
    required this.connectors,
    required this.connections,
    this.usageSummary,
  });

  @override
  List<Object?> get props => [connectors, connections, usageSummary];

  ConnectionLoaded copyWith({
    List<ConnectorMetadataModel>? connectors,
    List<DataConnectionModel>? connections,
    ConnectionUsageSummary? usageSummary,
  }) {
    return ConnectionLoaded(
      connectors: connectors ?? this.connectors,
      connections: connections ?? this.connections,
      usageSummary: usageSummary ?? this.usageSummary,
    );
  }

  /// Get connections grouped by category
  Map<DataCategory, List<DataConnectionModel>> get connectionsByCategory {
    final map = <DataCategory, List<DataConnectionModel>>{};
    for (final connection in connections) {
      final connector = connectors.firstWhere(
        (c) => c.id == connection.connectorId,
        orElse: () => ConnectorMetadataModel(
          id: connection.connectorId,
          name: connection.connectorName,
          displayName: connection.connectorName,
          displayNameZh: connection.connectorName,
          description: '',
          descriptionZh: '',
          icon: 'extension',
          category: DataCategory.other,
          authType: AuthType.oauth2,
          capabilities: const ConnectorCapabilities(),
          requiredScopes: const [],
          optionalScopes: const [],
          dataRetentionDays: 90,
          isAvailable: true,
          regions: const ['CN'],
          dataUsageDescription: '',
          dataUsageDescriptionZh: '',
        ),
      );
      map.putIfAbsent(connector.category, () => []).add(connection);
    }
    return map;
  }

  /// Get connectors grouped by category
  Map<DataCategory, List<ConnectorMetadataModel>> get connectorsByCategory {
    final map = <DataCategory, List<ConnectorMetadataModel>>{};
    for (final connector in connectors) {
      map.putIfAbsent(connector.category, () => []).add(connector);
    }
    return map;
  }
}

/// Error state
class ConnectionError extends DataConnectionState {
  final String message;
  final ConnectionLoaded? previousState;

  const ConnectionError(this.message, {this.previousState});

  @override
  List<Object?> get props => [message, previousState];
}

/// OAuth authorization required
class ConnectionAuthRequired extends DataConnectionState {
  final String connectionId;
  final String authUrl;
  final String connectorId;
  final String connectorName;
  final ConnectionLoaded? previousState;

  const ConnectionAuthRequired({
    required this.connectionId,
    required this.authUrl,
    required this.connectorId,
    required this.connectorName,
    this.previousState,
  });

  @override
  List<Object?> get props => [connectionId, authUrl, connectorId, connectorName, previousState];
}

/// Connection operation in progress
class ConnectionOperationInProgress extends DataConnectionState {
  final String operationType;
  final String? connectionId;
  final ConnectionLoaded previousState;

  const ConnectionOperationInProgress({
    required this.operationType,
    this.connectionId,
    required this.previousState,
  });

  @override
  List<Object?> get props => [operationType, connectionId, previousState];
}

/// Connection operation success
class ConnectionOperationSuccess extends DataConnectionState {
  final String message;
  final ConnectionLoaded currentState;

  const ConnectionOperationSuccess({
    required this.message,
    required this.currentState,
  });

  @override
  List<Object?> get props => [message, currentState];
}

/// Sync result state
class ConnectionSyncComplete extends DataConnectionState {
  final SyncResult result;
  final ConnectionLoaded currentState;

  const ConnectionSyncComplete({
    required this.result,
    required this.currentState,
  });

  @override
  List<Object?> get props => [result, currentState];
}
