import 'package:dartz/dartz.dart';

import '../../../../core/error/failures.dart';
import '../entities/connector_metadata.dart';
import '../entities/data_connection.dart';
import '../entities/connection_stats.dart';

/// Repository interface for data connection operations
abstract class DataConnectionRepository {
  /// List all available connectors
  Future<Either<Failure, List<ConnectorMetadata>>> getAvailableConnectors({
    DataCategory? category,
    String region = 'CN',
  });

  /// Get details of a specific connector
  Future<Either<Failure, ConnectorMetadata>> getConnectorDetails(String connectorId);

  /// List user's connections
  Future<Either<Failure, List<DataConnection>>> getUserConnections({
    bool includeDisconnected = false,
  });

  /// Get a specific connection
  Future<Either<Failure, DataConnection>> getConnection(String connectionId);

  /// Initiate a new connection (returns auth URL)
  Future<Either<Failure, InitiateConnectionResult>> initiateConnection({
    required String connectorId,
    String? redirectUri,
    List<String>? scopes,
  });

  /// Complete OAuth connection with authorization code
  Future<Either<Failure, DataConnection>> completeConnection({
    required String connectionId,
    required String code,
    String? state,
  });

  /// Disconnect a connection
  Future<Either<Failure, void>> disconnect(String connectionId);

  /// Update connection settings
  Future<Either<Failure, DataConnection>> updateConnectionSettings({
    required String connectionId,
    SyncFrequency? syncFrequency,
    bool? syncEnabled,
    UsagePermissions? usagePermissions,
  });

  /// Trigger manual sync
  Future<Either<Failure, SyncResult>> triggerSync({
    required String connectionId,
    bool fullSync = false,
  });

  /// Get connection statistics
  Future<Either<Failure, ConnectionStats>> getConnectionStats({
    required String connectionId,
    int sinceDays = 30,
  });

  /// Get usage summary across all connections
  Future<Either<Failure, ConnectionUsageSummary>> getUsageSummary();

  /// Get external calendar events from connected calendars
  Future<Either<Failure, List<Map<String, dynamic>>>> getExternalCalendarEvents({
    required DateTime startDate,
    required DateTime endDate,
  });

  /// Get external travel bookings (flights, hotels from parsed emails)
  Future<Either<Failure, List<Map<String, dynamic>>>> getExternalTravelBookings({
    required DateTime startDate,
    required DateTime endDate,
  });
}

/// Result of initiating a connection
class InitiateConnectionResult {
  final String connectionId;
  final String authUrl;
  final String connectorId;
  final String connectorName;

  const InitiateConnectionResult({
    required this.connectionId,
    required this.authUrl,
    required this.connectorId,
    required this.connectorName,
  });
}
