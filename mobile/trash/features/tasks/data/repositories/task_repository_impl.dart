import 'package:dartz/dartz.dart';
import '../../../../core/error/exceptions.dart';
import '../../../../core/error/failures.dart';
import '../../domain/entities/family_task.dart';
import '../../domain/repositories/task_repository.dart';
import '../datasources/task_remote_datasource.dart';
import '../models/family_task_model.dart';

class TaskRepositoryImpl implements TaskRepository {
  final TaskRemoteDataSource remoteDataSource;

  TaskRepositoryImpl({required this.remoteDataSource});

  @override
  Future<Either<Failure, List<FamilyTask>>> getTasks({
    TaskStatus? status,
    String? taskType,
    DateTime? startDate,
    DateTime? endDate,
  }) async {
    try {
      final tasks = await remoteDataSource.getTasks(
        status: status != null
            ? (status == TaskStatus.inProgress ? 'in_progress' : status.name)
            : null,
        taskType: taskType,
        startDate: startDate,
        endDate: endDate,
      );
      return Right(tasks);
    } on AppException catch (e) {
      return Left(ServerFailure(e.message));
    }
  }

  @override
  Future<Either<Failure, FamilyTask>> getTask(String taskId) async {
    try {
      final task = await remoteDataSource.getTask(taskId);
      return Right(task);
    } on AppException catch (e) {
      return Left(ServerFailure(e.message));
    }
  }

  @override
  Future<Either<Failure, FamilyTask>> createTask(FamilyTask task) async {
    try {
      final model = FamilyTaskModel(
        id: task.id,
        familyId: task.familyId,
        parentTaskId: task.parentTaskId,
        title: task.title,
        description: task.description,
        taskType: task.taskType,
        creatorId: task.creatorId,
        assigneeId: task.assigneeId,
        dueDate: task.dueDate,
        dueTime: task.dueTime,
        priority: task.priority,
        status: task.status,
        completedAt: task.completedAt,
        metadata: task.metadata,
        createdAt: task.createdAt,
        updatedAt: task.updatedAt,
      );
      final result = await remoteDataSource.createTask(model);
      return Right(result);
    } on AppException catch (e) {
      return Left(ServerFailure(e.message));
    }
  }

  @override
  Future<Either<Failure, FamilyTask>> updateTask(String taskId, FamilyTask task) async {
    try {
      final model = FamilyTaskModel(
        id: task.id,
        familyId: task.familyId,
        parentTaskId: task.parentTaskId,
        title: task.title,
        description: task.description,
        taskType: task.taskType,
        creatorId: task.creatorId,
        assigneeId: task.assigneeId,
        dueDate: task.dueDate,
        dueTime: task.dueTime,
        priority: task.priority,
        status: task.status,
        completedAt: task.completedAt,
        metadata: task.metadata,
        createdAt: task.createdAt,
        updatedAt: task.updatedAt,
      );
      final result = await remoteDataSource.updateTask(taskId, model);
      return Right(result);
    } on AppException catch (e) {
      return Left(ServerFailure(e.message));
    }
  }

  @override
  Future<Either<Failure, void>> deleteTask(String taskId) async {
    try {
      await remoteDataSource.deleteTask(taskId);
      return const Right(null);
    } on AppException catch (e) {
      return Left(ServerFailure(e.message));
    }
  }

  @override
  Future<Either<Failure, void>> completeTask(String taskId) async {
    try {
      await remoteDataSource.completeTask(taskId);
      return const Right(null);
    } on AppException catch (e) {
      return Left(ServerFailure(e.message));
    }
  }
}
