import '../../../../core/network/api_client.dart';

/// Remote datasource for fetching pending actions.
///
/// Used by the reconnect-compensation flow to sync any confirm cards
/// that were missed while the user was offline.
class PendingActionDatasource {
  final ApiClient _apiClient;

  PendingActionDatasource(this._apiClient);

  /// Fetch all pending (non-expired) actions for the current user.
  ///
  /// Maps to `GET /actions/pending`.
  Future<List<Map<String, dynamic>>> fetchPending() async {
    final response = await _apiClient.get<List<dynamic>>(
      '/actions/pending',
      parser: (data) => (data as List).cast<Map<String, dynamic>>(),
    );
    return response.cast<Map<String, dynamic>>();
  }
}
