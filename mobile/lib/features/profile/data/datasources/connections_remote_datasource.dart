import '../../../../core/network/api_client.dart';
import '../models/connection_model.dart';

class ConnectionsRemoteDataSource {
  final ApiClient _client;

  ConnectionsRemoteDataSource(this._client);

  /// Fetch all user connections
  Future<List<UserConnection>> fetchConnections() async {
    final response = await _client.get<List<dynamic>>('/connections/');
    return response
        .map((e) => UserConnection.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  /// Fetch available providers that can be connected.
  /// Backend returns grouped structure: [{provider_type, providers: [...]}]
  /// We flatten it into a single list of AvailableProvider.
  Future<List<AvailableProvider>> fetchAvailableProviders() async {
    final response = await _client.get<List<dynamic>>('/connections/available');
    final providers = <AvailableProvider>[];
    for (final group in response) {
      final groupMap = group as Map<String, dynamic>;
      final providerList = groupMap['providers'] as List<dynamic>? ?? [];
      for (final p in providerList) {
        providers.add(AvailableProvider.fromJson(p as Map<String, dynamic>));
      }
    }
    return providers;
  }

  /// Initiate connection to a provider
  Future<Map<String, dynamic>> connectProvider(String providerName) async {
    final response = await _client
        .post<Map<String, dynamic>>('/connections/$providerName/authorize');
    return response;
  }

  /// Disconnect a provider
  Future<void> disconnectProvider(String connectionId) async {
    await _client.delete('/connections/$connectionId');
  }

  /// Update connection settings (scopes, sync frequency)
  Future<UserConnection> updateConnection(
    String connectionId,
    Map<String, dynamic> data,
  ) async {
    final response = await _client.patch<Map<String, dynamic>>(
      '/connections/$connectionId',
      data: data,
    );
    return UserConnection.fromJson(response);
  }

  /// Trigger manual sync for a connection
  Future<void> syncConnection(String connectionId) async {
    await _client.post('/connections/$connectionId/sync');
  }

  /// Create a custom MCP connection.
  ///
  /// Uses the display name (lowercased, spaces→underscores) as provider_name
  /// since custom MCP connections don't come from the built-in catalog.
  Future<Map<String, dynamic>> createCustomConnection({
    required String displayName,
    required String mcpServerUrl,
    Map<String, dynamic>? mcpServerConfig,
  }) async {
    final providerName = displayName
        .trim()
        .toLowerCase()
        .replaceAll(RegExp(r'\s+'), '_')
        .replaceAll(RegExp(r'[^a-z0-9_]'), '');
    final response = await _client.post<Map<String, dynamic>>(
      '/connections/custom',
      data: {
        'provider_name': providerName.isNotEmpty ? providerName : 'custom_mcp',
        'display_name': displayName,
        'auth_type': 'mcp_direct',
        'mcp_server_url': mcpServerUrl,
        if (mcpServerConfig != null) 'mcp_server_config': mcpServerConfig,
      },
    );
    return response;
  }
}
