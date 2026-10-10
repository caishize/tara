import '../../../../core/network/api_client.dart';
import '../models/smart_suggestion_model.dart';
import '../models/memory_model.dart';

/// Remote data source for secretary API
abstract class SecretaryRemoteDataSource {
  /// Get smart suggestions for the current user
  Future<SuggestionListResponse> getSuggestions({
    String? familyId,
    int limit = 10,
  });

  /// Execute an action from a suggestion
  Future<SuggestionActionResponse> executeAction(
    SuggestionActionRequest request,
  );

  /// Dismiss a suggestion
  Future<void> dismissSuggestion(String suggestionId);

  /// Get available suggestion types
  Future<List<Map<String, dynamic>>> getSuggestionTypes();

  // ===== Memory APIs =====

  /// Get user memories
  Future<MemoryListResponse> getMemories({
    String? memoryType,
    String? status,
    int limit = 50,
    int offset = 0,
  });

  /// Delete a memory
  Future<void> deleteMemory(String memoryId);

  /// Update memory status
  Future<MemoryModel> updateMemoryStatus(String memoryId, String status);

  /// Recall memories based on a message
  Future<MemoryRecallResponse> recallMemories(String message, {int limit = 5});

  /// Search memories by query
  Future<List<MemoryModel>> searchMemories(
    String query, {
    String? searchType,
    int limit = 10,
  });

  // ===== Insight APIs =====

  /// Get active insights
  Future<List<InsightModel>> getInsights({
    String? insightType,
    String? status,
    int limit = 20,
  });

  /// Execute an insight action
  Future<InsightActionResponse> executeInsightAction(
    String insightId,
    String action, {
    Map<String, dynamic>? params,
  });

  /// Generate insights (for daily briefing)
  Future<List<InsightModel>> generateInsights();
}

/// Response model for memory list
class MemoryListResponse {
  final List<MemoryModel> memories;
  final int total;
  final bool hasMore;

  const MemoryListResponse({
    required this.memories,
    required this.total,
    this.hasMore = false,
  });

  factory MemoryListResponse.fromJson(Map<String, dynamic> json) {
    return MemoryListResponse(
      memories: (json['memories'] as List<dynamic>?)
              ?.map((e) => MemoryModel.fromJson(e as Map<String, dynamic>))
              .toList() ??
          const [],
      total: json['total'] as int? ?? 0,
      hasMore: json['has_more'] as bool? ?? false,
    );
  }
}

/// Response model for memory recall
class MemoryRecallResponse {
  final List<MemoryModel> memories;
  final String? contextString;

  const MemoryRecallResponse({
    required this.memories,
    this.contextString,
  });

  factory MemoryRecallResponse.fromJson(Map<String, dynamic> json) {
    return MemoryRecallResponse(
      memories: (json['memories'] as List<dynamic>?)
              ?.map((e) => MemoryModel.fromJson(e as Map<String, dynamic>))
              .toList() ??
          const [],
      contextString: json['context_string'] as String?,
    );
  }
}

/// Response model for insight action
class InsightActionResponse {
  final bool success;
  final String message;
  final Map<String, dynamic>? data;

  const InsightActionResponse({
    required this.success,
    required this.message,
    this.data,
  });

  factory InsightActionResponse.fromJson(Map<String, dynamic> json) {
    return InsightActionResponse(
      success: json['success'] as bool? ?? false,
      message: json['message'] as String? ?? '',
      data: json['data'] as Map<String, dynamic>?,
    );
  }
}

class SecretaryRemoteDataSourceImpl implements SecretaryRemoteDataSource {
  final ApiClient _apiClient;

  SecretaryRemoteDataSourceImpl(this._apiClient);

  static const String _basePath = '/secretary';

  @override
  Future<SuggestionListResponse> getSuggestions({
    String? familyId,
    int limit = 10,
  }) async {
    final queryParams = <String, dynamic>{
      'limit': limit,
    };
    if (familyId != null) queryParams['family_id'] = familyId;

    return await _apiClient.get<SuggestionListResponse>(
      '$_basePath/suggestions',
      queryParameters: queryParams,
      parser: (data) => SuggestionListResponse.fromJson(data as Map<String, dynamic>),
    );
  }

  @override
  Future<SuggestionActionResponse> executeAction(
    SuggestionActionRequest request,
  ) async {
    return await _apiClient.post<SuggestionActionResponse>(
      '$_basePath/suggestions/action',
      data: request.toJson(),
      parser: (data) => SuggestionActionResponse.fromJson(data as Map<String, dynamic>),
    );
  }

  @override
  Future<void> dismissSuggestion(String suggestionId) async {
    await _apiClient.post('$_basePath/suggestions/$suggestionId/dismiss');
  }

  @override
  Future<List<Map<String, dynamic>>> getSuggestionTypes() async {
    return await _apiClient.get<List<Map<String, dynamic>>>(
      '$_basePath/suggestions/types',
      parser: (data) {
        final types = data['types'] as List<dynamic>? ?? [];
        return types.map((e) => e as Map<String, dynamic>).toList();
      },
    );
  }

  // ===== Memory API Implementations =====

  @override
  Future<MemoryListResponse> getMemories({
    String? memoryType,
    String? status,
    int limit = 50,
    int offset = 0,
  }) async {
    final queryParams = <String, dynamic>{
      'limit': limit,
      'offset': offset,
    };
    if (memoryType != null) queryParams['memory_type'] = memoryType;
    if (status != null) queryParams['status'] = status;

    return await _apiClient.get<MemoryListResponse>(
      '$_basePath/memories',
      queryParameters: queryParams,
      parser: (data) => MemoryListResponse.fromJson(data as Map<String, dynamic>),
    );
  }

  @override
  Future<void> deleteMemory(String memoryId) async {
    await _apiClient.delete('$_basePath/memories/$memoryId');
  }

  @override
  Future<MemoryModel> updateMemoryStatus(String memoryId, String status) async {
    return await _apiClient.patch<MemoryModel>(
      '$_basePath/memories/$memoryId/status',
      data: {'status': status},
      parser: (data) => MemoryModel.fromJson(data as Map<String, dynamic>),
    );
  }

  @override
  Future<MemoryRecallResponse> recallMemories(String message, {int limit = 5}) async {
    return await _apiClient.get<MemoryRecallResponse>(
      '$_basePath/memories/recall',
      queryParameters: {
        'message': message,
        'limit': limit,
      },
      parser: (data) => MemoryRecallResponse.fromJson(data as Map<String, dynamic>),
    );
  }

  @override
  Future<List<MemoryModel>> searchMemories(
    String query, {
    String? searchType,
    int limit = 10,
  }) async {
    final queryParams = <String, dynamic>{
      'q': query,
      'limit': limit,
    };
    if (searchType != null) queryParams['type'] = searchType;

    return await _apiClient.get<List<MemoryModel>>(
      '$_basePath/memories/search',
      queryParameters: queryParams,
      parser: (data) {
        final memories = data['memories'] as List<dynamic>? ?? [];
        return memories.map((e) => MemoryModel.fromJson(e as Map<String, dynamic>)).toList();
      },
    );
  }

  // ===== Insight API Implementations =====

  @override
  Future<List<InsightModel>> getInsights({
    String? insightType,
    String? status,
    int limit = 20,
  }) async {
    final queryParams = <String, dynamic>{
      'limit': limit,
    };
    if (insightType != null) queryParams['insight_type'] = insightType;
    if (status != null) queryParams['status'] = status;

    return await _apiClient.get<List<InsightModel>>(
      '$_basePath/insights',
      queryParameters: queryParams,
      parser: (data) {
        final insights = data['insights'] as List<dynamic>? ?? [];
        return insights.map((e) => InsightModel.fromJson(e as Map<String, dynamic>)).toList();
      },
    );
  }

  @override
  Future<InsightActionResponse> executeInsightAction(
    String insightId,
    String action, {
    Map<String, dynamic>? params,
  }) async {
    return await _apiClient.post<InsightActionResponse>(
      '$_basePath/insights/$insightId/action',
      data: {
        'action': action,
        if (params != null) 'params': params,
      },
      parser: (data) => InsightActionResponse.fromJson(data as Map<String, dynamic>),
    );
  }

  @override
  Future<List<InsightModel>> generateInsights() async {
    return await _apiClient.post<List<InsightModel>>(
      '$_basePath/insights/generate',
      parser: (data) {
        final insights = data['insights'] as List<dynamic>? ?? [];
        return insights.map((e) => InsightModel.fromJson(e as Map<String, dynamic>)).toList();
      },
    );
  }
}
