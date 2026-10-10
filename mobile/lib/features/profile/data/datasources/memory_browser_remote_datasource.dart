import '../../../../core/network/api_client.dart';
import '../models/memory_item_model.dart';

class MemoryBrowserRemoteDataSource {
  final ApiClient _client;

  MemoryBrowserRemoteDataSource(this._client);

  /// Fetch memories with optional type filter and offset-based pagination.
  /// Backend uses offset/limit, not page-based pagination.
  Future<MemoryListResponse> fetchMemories({
    String? type,
    int offset = 0,
    int limit = 20,
  }) async {
    final queryParams = <String, dynamic>{
      'offset': offset.toString(),
      'limit': limit.toString(),
      'status': 'active',
    };
    if (type != null) queryParams['memory_type'] = type;

    final response = await _client.get<Map<String, dynamic>>(
      '/memory/list',
      queryParameters: queryParams,
    );
    return MemoryListResponse.fromJson(
      response,
      requestOffset: offset,
      requestLimit: limit,
    );
  }

  /// Fetch a single memory by ID.
  Future<MemoryItem> fetchMemoryById(String memoryId) async {
    final response = await _client.get<Map<String, dynamic>>(
      '/memory/detail/$memoryId',
    );
    return MemoryItem.fromJson(response);
  }

  /// Semantic search for memories using recall endpoint.
  Future<List<MemoryItem>> searchMemories(String query) async {
    final response = await _client.get<Map<String, dynamic>>(
      '/memory/recall',
      queryParameters: {'query': query},
    );
    // Backend returns {"memories": [...], "context_summary": "...", "recall_count": N}
    final items = response['memories'] as List<dynamic>? ?? [];
    return items
        .map((e) => MemoryItem.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  /// Archive a memory
  Future<void> archiveMemory(String memoryId) async {
    await _client.patch(
      '/memory/$memoryId/status',
      data: {'status': 'archived'},
    );
  }

  /// Delete a memory
  Future<void> deleteMemory(String memoryId) async {
    await _client.delete('/memory/$memoryId');
  }

  /// Fetch pending insights.
  /// Backend returns {"insights": [...], "total": N}
  Future<List<InsightItem>> fetchInsights({int limit = 10}) async {
    final response = await _client.get<Map<String, dynamic>>(
      '/memory/insights',
      queryParameters: {'limit': limit.toString()},
    );
    final items = response['insights'] as List<dynamic>? ?? [];
    return items
        .map((e) => InsightItem.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  /// Fetch all insights (for insight history page) with optional type filter.
  /// Passes include_all=true to get all insights regardless of status/expiry.
  Future<List<InsightItem>> fetchAllInsights({
    String? type,
    int limit = 50,
  }) async {
    final queryParams = <String, dynamic>{
      'limit': limit.toString(),
      'include_all': 'true',
    };
    if (type != null) queryParams['type'] = type;

    final response = await _client.get<Map<String, dynamic>>(
      '/memory/insights',
      queryParameters: queryParams,
    );
    final items = response['insights'] as List<dynamic>? ?? [];
    return items
        .map((e) => InsightItem.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  /// Submit feedback on an insight
  Future<void> submitInsightFeedback(String insightId, String feedbackType) async {
    await _client.post(
      '/memory/insights/$insightId/feedback',
      data: {'feedback_type': feedbackType},
    );
  }
}
