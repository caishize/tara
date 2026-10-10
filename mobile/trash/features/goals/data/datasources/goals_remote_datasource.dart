import '../../../../core/network/api_client.dart';
import '../models/goal_model.dart';

/// Goals remote data source
class GoalsRemoteDataSource {
  final ApiClient _apiClient;

  GoalsRemoteDataSource({required ApiClient apiClient}) : _apiClient = apiClient;

  /// Get goals for a member
  Future<List<GoalModel>> getMemberGoals({
    required String memberId,
    String? status,
    String? goalType,
  }) async {
    final queryParams = <String, String>{
      'member_id': memberId,
      if (status != null) 'status': status,
      if (goalType != null) 'goal_type': goalType,
    };
    final queryString = queryParams.entries.map((e) => '${e.key}=${e.value}').join('&');
    final response = await _apiClient.get('/goals?$queryString');
    final List<dynamic> data = response is List ? response : [];
    return data.map((e) => GoalModel.fromJson(e as Map<String, dynamic>)).toList();
  }

  /// Get goals for a family
  Future<List<GoalModel>> getFamilyGoals({
    required String familyId,
    String? status,
  }) async {
    final queryParams = <String, String>{
      'family_id': familyId,
      if (status != null) 'status': status,
    };
    final queryString = queryParams.entries.map((e) => '${e.key}=${e.value}').join('&');
    final response = await _apiClient.get('/goals?$queryString');
    final List<dynamic> data = response is List ? response : [];
    return data.map((e) => GoalModel.fromJson(e as Map<String, dynamic>)).toList();
  }

  /// Get a single goal by ID
  Future<GoalModel> getGoal(String goalId) async {
    final response = await _apiClient.get('/goals/$goalId');
    return GoalModel.fromJson(response as Map<String, dynamic>);
  }

  /// Create a new goal
  Future<GoalModel> createGoal({
    required String memberId,
    required String goalType,
    required String description,
    required double targetValue,
    required String unit,
    required DateTime startDate,
    required DateTime endDate,
  }) async {
    final response = await _apiClient.post('/goals', data: {
      'member_id': memberId,
      'goal_type': goalType,
      'description': description,
      'target_value': targetValue,
      'unit': unit,
      'start_date': startDate.toIso8601String().split('T').first,
      'end_date': endDate.toIso8601String().split('T').first,
    });
    return GoalModel.fromJson(response as Map<String, dynamic>);
  }

  /// Update a goal
  Future<GoalModel> updateGoal({
    required String goalId,
    required String memberId,
    String? description,
    double? targetValue,
    DateTime? endDate,
    String? status,
  }) async {
    final response = await _apiClient.patch('/goals/$goalId?member_id=$memberId', data: {
      if (description != null) 'description': description,
      if (targetValue != null) 'target_value': targetValue,
      if (endDate != null) 'end_date': endDate.toIso8601String().split('T').first,
      if (status != null) 'status': status,
    });
    return GoalModel.fromJson(response as Map<String, dynamic>);
  }

  /// Record progress for a goal
  Future<void> recordProgress({
    required String goalId,
    required String memberId,
    required double progressIncrement,
    String? notes,
    DateTime? recordDate,
  }) async {
    await _apiClient.post('/goals/$goalId/progress?member_id=$memberId', data: {
      'progress_increment': progressIncrement,
      if (notes != null) 'notes': notes,
      if (recordDate != null) 'record_date': recordDate.toIso8601String().split('T').first,
    });
  }

  /// Get weekly summary for a goal
  Future<WeeklySummaryModel> getWeeklySummary(String goalId) async {
    final response = await _apiClient.get('/goals/$goalId/weekly-summary');
    return WeeklySummaryModel.fromJson(response as Map<String, dynamic>);
  }
}
