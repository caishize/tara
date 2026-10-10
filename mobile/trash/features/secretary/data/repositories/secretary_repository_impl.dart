import '../../../../core/network/api_client.dart';
import '../../domain/entities/smart_suggestion.dart';
import '../../domain/entities/daily_briefing.dart';
import '../../domain/repositories/secretary_repository.dart';
import '../datasources/secretary_remote_datasource.dart';
import '../models/smart_suggestion_model.dart';
import '../models/daily_briefing_model.dart';
import '../models/memory_model.dart';

/// Implementation of SecretaryRepository
class SecretaryRepositoryImpl implements SecretaryRepository {
  final SecretaryRemoteDataSource _remoteDataSource;
  final ApiClient _apiClient;

  SecretaryRepositoryImpl(this._remoteDataSource, this._apiClient);

  @override
  Future<List<SmartSuggestion>> getSuggestions({
    String? familyId,
    int limit = 10,
  }) async {
    final response = await _remoteDataSource.getSuggestions(
      familyId: familyId,
      limit: limit,
    );
    return response.suggestions;
  }

  @override
  Future<SuggestionActionResponse> executeAction({
    required String suggestionId,
    required String action,
    Map<String, dynamic>? params,
  }) async {
    return await _remoteDataSource.executeAction(
      SuggestionActionRequest(
        suggestionId: suggestionId,
        action: action,
        params: params,
      ),
    );
  }

  @override
  Future<void> dismissSuggestion(String suggestionId) async {
    await _remoteDataSource.dismissSuggestion(suggestionId);
  }

  @override
  Future<DailyBriefing> getDailyBriefing({DateTime? targetDate}) async {
    final queryParams = <String, dynamic>{};
    if (targetDate != null) {
      queryParams['date'] = '${targetDate.year}-${targetDate.month.toString().padLeft(2, '0')}-${targetDate.day.toString().padLeft(2, '0')}';
    }

    return await _apiClient.get<DailyBriefing>(
      '/secretary/daily-briefing',
      queryParameters: queryParams,
      parser: (data) => DailyBriefingModel.fromJson(data as Map<String, dynamic>).toEntity(),
    );
  }

  // ===== Memory Method Implementations =====

  @override
  Future<MemoryListResponse> getMemories({
    String? memoryType,
    String? status,
    int limit = 50,
    int offset = 0,
  }) async {
    return await _remoteDataSource.getMemories(
      memoryType: memoryType,
      status: status,
      limit: limit,
      offset: offset,
    );
  }

  @override
  Future<void> deleteMemory(String memoryId) async {
    await _remoteDataSource.deleteMemory(memoryId);
  }

  @override
  Future<MemoryModel> updateMemoryStatus(String memoryId, String status) async {
    return await _remoteDataSource.updateMemoryStatus(memoryId, status);
  }

  @override
  Future<MemoryRecallResponse> recallMemories(String message, {int limit = 5}) async {
    return await _remoteDataSource.recallMemories(message, limit: limit);
  }

  @override
  Future<List<MemoryModel>> searchMemories(
    String query, {
    String? searchType,
    int limit = 10,
  }) async {
    return await _remoteDataSource.searchMemories(
      query,
      searchType: searchType,
      limit: limit,
    );
  }

  // ===== Insight Method Implementations =====

  @override
  Future<List<InsightModel>> getInsights({
    String? insightType,
    String? status,
    int limit = 20,
  }) async {
    return await _remoteDataSource.getInsights(
      insightType: insightType,
      status: status,
      limit: limit,
    );
  }

  @override
  Future<InsightActionResponse> executeInsightAction(
    String insightId,
    String action, {
    Map<String, dynamic>? params,
  }) async {
    return await _remoteDataSource.executeInsightAction(
      insightId,
      action,
      params: params,
    );
  }

  @override
  Future<List<InsightModel>> generateInsights() async {
    return await _remoteDataSource.generateInsights();
  }
}
