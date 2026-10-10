import 'package:dartz/dartz.dart';
import '../../../../core/error/failures.dart';
import '../entities/family_task.dart';

abstract class TaskRepository {
  /// Get all tasks for the family
  Future<Either<Failure, List<FamilyTask>>> getTasks({
    TaskStatus? status,
    String? taskType,
    DateTime? startDate,
    DateTime? endDate,
  });

  /// Get a single task by ID
  Future<Either<Failure, FamilyTask>> getTask(String taskId);

  /// Create a new task
  Future<Either<Failure, FamilyTask>> createTask(FamilyTask task);

  /// Update a task
  Future<Either<Failure, FamilyTask>> updateTask(String taskId, FamilyTask task);

  /// Delete a task
  Future<Either<Failure, void>> deleteTask(String taskId);

  /// Complete a task
  Future<Either<Failure, void>> completeTask(String taskId);
}
