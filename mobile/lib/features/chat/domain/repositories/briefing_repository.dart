import '../entities/smart_suggestion.dart';
import '../entities/daily_briefing.dart';
import '../../data/models/smart_suggestion_model.dart';
import '../../data/models/memory_model.dart';
import '../../data/datasources/briefing_remote_datasource.dart';

/// Repository interface for secretary operations
abstract class SecretaryRepository {
  /// Get smart suggestions
  Future<List<SmartSuggestion>> getSuggestions({
    String? familyId,
    int limit = 10,
  });

  /// Execute a suggestion action
  Future<SuggestionActionResponse> executeAction({
    required String suggestionId,
    required String action,
    Map<String, dynamic>? params,
  });

  /// Dismiss a suggestion
  Future<void> dismissSuggestion(String suggestionId);

  /// Get daily briefing
  Future<DailyBriefing> getDailyBriefing({DateTime? targetDate});

  // ===== Memory Methods =====

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

  /// Search memories
  Future<List<MemoryModel>> searchMemories(
    String query, {
    String? searchType,
    int limit = 10,
  });

  // ===== Insight Methods =====

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

  /// Generate insights
  Future<List<InsightModel>> generateInsights();
}
