import '../../../../core/network/api_client.dart';
import '../models/connector_metadata_model.dart';
import '../models/data_connection_model.dart';
import '../models/connection_stats_model.dart';
import '../../domain/entities/data_connection.dart';

class ConnectionRemoteDataSource {
  final ApiClient _client;

  ConnectionRemoteDataSource(this._client);

  /// Get available connectors
  Future<List<ConnectorMetadataModel>> getAvailableConnectors({
    String? category,
    String region = 'CN',
  }) async {
    final queryParams = <String, String>{
      'region': region,
    };
    if (category != null) {
      queryParams['category'] = category;
    }

    final response = await _client.get<Map<String, dynamic>>(
      '/connections/connectors',
      queryParameters: queryParams,
    );

    final connectors = (response['connectors'] as List<dynamic>)
        .map((e) => ConnectorMetadataModel.fromJson(e as Map<String, dynamic>))
        .toList();

    return connectors;
  }

  /// Get connector details
  Future<ConnectorMetadataModel> getConnectorDetails(String connectorId) async {
    final response = await _client.get<Map<String, dynamic>>(
      '/connections/connectors/$connectorId',
    );
    return ConnectorMetadataModel.fromJson(response);
  }

  /// Get user connections
  Future<List<DataConnectionModel>> getUserConnections({
    bool includeDisconnected = false,
  }) async {
    final response = await _client.get<Map<String, dynamic>>(
      '/connections',
      queryParameters: {
        'include_disconnected': includeDisconnected.toString(),
      },
    );

    final connections = (response['connections'] as List<dynamic>)
        .map((e) => DataConnectionModel.fromJson(e as Map<String, dynamic>))
        .toList();

    return connections;
  }

  /// Get a specific connection
  Future<DataConnectionModel> getConnection(String connectionId) async {
    final response = await _client.get<Map<String, dynamic>>(
      '/connections/$connectionId',
    );
    return DataConnectionModel.fromJson(response);
  }

  /// Initiate a connection
  Future<Map<String, dynamic>> initiateConnection({
    required String connectorId,
    String? redirectUri,
    List<String>? scopes,
  }) async {
    final response = await _client.post<Map<String, dynamic>>(
      '/connections/initiate',
      data: {
        'connector_id': connectorId,
        if (redirectUri != null) 'redirect_uri': redirectUri,
        if (scopes != null) 'scopes': scopes,
      },
    );
    return response;
  }

  /// Complete connection with OAuth code
  Future<DataConnectionModel> completeConnection({
    required String connectionId,
    required String code,
    String? state,
  }) async {
    final response = await _client.post<Map<String, dynamic>>(
      '/connections/$connectionId/complete',
      data: {
        'code': code,
        if (state != null) 'state': state,
      },
    );
    return DataConnectionModel.fromJson(response);
  }

  /// Disconnect a connection
  Future<void> disconnect(String connectionId) async {
    await _client.delete('/connections/$connectionId');
  }

  /// Update connection settings
  Future<DataConnectionModel> updateConnectionSettings({
    required String connectionId,
    SyncFrequency? syncFrequency,
    bool? syncEnabled,
    UsagePermissions? usagePermissions,
  }) async {
    final response = await _client.patch<Map<String, dynamic>>(
      '/connections/$connectionId/settings',
      data: {
        if (syncFrequency != null) 'sync_frequency': syncFrequency.name,
        if (syncEnabled != null) 'sync_enabled': syncEnabled,
        if (usagePermissions != null) 'usage_permissions': usagePermissions.toJson(),
      },
    );
    return DataConnectionModel.fromJson(response);
  }

  /// Trigger manual sync
  Future<SyncResultModel> triggerSync({
    required String connectionId,
    bool fullSync = false,
  }) async {
    final response = await _client.post<Map<String, dynamic>>(
      '/connections/$connectionId/sync',
      queryParameters: {
        'full_sync': fullSync.toString(),
      },
    );
    return SyncResultModel.fromJson(response);
  }

  /// Get connection stats
  Future<ConnectionStatsModel> getConnectionStats({
    required String connectionId,
    int sinceDays = 30,
  }) async {
    final response = await _client.get<Map<String, dynamic>>(
      '/connections/$connectionId/stats',
      queryParameters: {
        'since_days': sinceDays.toString(),
      },
    );
    return ConnectionStatsModel.fromJson(response);
  }

  /// Get usage summary
  Future<ConnectionUsageSummaryModel> getUsageSummary() async {
    try {
      final response = await _client.get<Map<String, dynamic>>(
        '/connections/usage-summary',
      );
      return ConnectionUsageSummaryModel.fromJson(response);
    } catch (e) {
      // Return empty summary if API not available
      return ConnectionUsageSummaryModel(
        calendarEventsSynced: 0,
        emailsParsed: 0,
        ordersParsed: 0,
        suggestionsGenerated: 0,
        periodStart: DateTime.now().subtract(const Duration(days: 30)),
        periodEnd: DateTime.now(),
      );
    }
  }

  /// Get external calendar events
  Future<List<Map<String, dynamic>>> getExternalCalendarEvents({
    required DateTime startDate,
    required DateTime endDate,
  }) async {
    try {
      final response = await _client.get<Map<String, dynamic>>(
        '/connections/calendar-events',
        queryParameters: {
          'start_date': startDate.toIso8601String().split('T')[0],
          'end_date': endDate.toIso8601String().split('T')[0],
        },
      );
      return (response['events'] as List<dynamic>?)
              ?.map((e) => e as Map<String, dynamic>)
              .toList() ??
          [];
    } catch (e) {
      // Return empty list if API not available or error
      return [];
    }
  }

  /// Get external travel bookings (flights, hotels)
  Future<List<Map<String, dynamic>>> getExternalTravelBookings({
    required DateTime startDate,
    required DateTime endDate,
  }) async {
    try {
      final response = await _client.get<Map<String, dynamic>>(
        '/connections/travel-bookings',
        queryParameters: {
          'start_date': startDate.toIso8601String().split('T')[0],
          'end_date': endDate.toIso8601String().split('T')[0],
        },
      );
      return (response['bookings'] as List<dynamic>?)
              ?.map((e) => e as Map<String, dynamic>)
              .toList() ??
          [];
    } catch (e) {
      // Return empty list if API not available or error
      return [];
    }
  }
}
