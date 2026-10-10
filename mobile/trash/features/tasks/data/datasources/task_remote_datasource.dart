import '../../../../core/network/api_client.dart';
import '../../domain/entities/family_task.dart';
import '../models/family_task_model.dart';

abstract class TaskRemoteDataSource {
  Future<List<FamilyTaskModel>> getTasks({
    String? status,
    String? taskType,
    DateTime? startDate,
    DateTime? endDate,
  });

  Future<FamilyTaskModel> getTask(String taskId);

  Future<FamilyTaskModel> createTask(FamilyTaskModel task);

  Future<FamilyTaskModel> updateTask(String taskId, FamilyTaskModel task);

  Future<void> deleteTask(String taskId);

  Future<void> completeTask(String taskId);
}

class TaskRemoteDataSourceImpl implements TaskRemoteDataSource {
  final ApiClient _apiClient;

  TaskRemoteDataSourceImpl(this._apiClient);

  static const String _basePath = '/assistant/tasks';

  @override
  Future<List<FamilyTaskModel>> getTasks({
    String? status,
    String? taskType,
    DateTime? startDate,
    DateTime? endDate,
  }) async {
    final queryParams = <String, dynamic>{};
    if (status != null) queryParams['status'] = status;
    if (taskType != null) queryParams['task_type'] = taskType;
    if (startDate != null) queryParams['start_date'] = startDate.toIso8601String().split('T')[0];
    if (endDate != null) queryParams['end_date'] = endDate.toIso8601String().split('T')[0];

    return await _apiClient.get<List<FamilyTaskModel>>(
      _basePath,
      queryParameters: queryParams,
      parser: (data) {
        final items = data['tasks'] as List? ?? data['items'] as List? ?? data as List? ?? [];
        return items
            .map((e) => FamilyTaskModel.fromJson(e as Map<String, dynamic>))
            .toList();
      },
    );
  }

  @override
  Future<FamilyTaskModel> getTask(String taskId) async {
    return await _apiClient.get<FamilyTaskModel>(
      '$_basePath/$taskId',
      parser: (data) => FamilyTaskModel.fromJson(data as Map<String, dynamic>),
    );
  }

  @override
  Future<FamilyTaskModel> createTask(FamilyTaskModel task) async {
    return await _apiClient.post<FamilyTaskModel>(
      _basePath,
      data: task.toJson(),
      parser: (data) => FamilyTaskModel.fromJson(data as Map<String, dynamic>),
    );
  }

  @override
  Future<FamilyTaskModel> updateTask(String taskId, FamilyTaskModel task) async {
    return await _apiClient.put<FamilyTaskModel>(
      '$_basePath/$taskId',
      data: task.toJson(),
      parser: (data) => FamilyTaskModel.fromJson(data as Map<String, dynamic>),
    );
  }

  @override
  Future<void> deleteTask(String taskId) async {
    await _apiClient.delete('$_basePath/$taskId');
  }

  @override
  Future<void> completeTask(String taskId) async {
    await _apiClient.post('$_basePath/$taskId/complete');
  }
}
