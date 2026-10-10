import 'package:dartz/dartz.dart';
import '../../../../core/error/failures.dart';
import '../../../../core/error/exceptions.dart';
import '../../domain/entities/goal.dart';
import '../../domain/repositories/goals_repository.dart';
import '../datasources/goals_remote_datasource.dart';

/// Goals repository implementation
class GoalsRepositoryImpl implements GoalsRepository {
  final GoalsRemoteDataSource remoteDataSource;

  GoalsRepositoryImpl({required this.remoteDataSource});

  @override
  Future<Either<Failure, List<Goal>>> getMemberGoals({
    required String memberId,
    String? status,
    String? goalType,
  }) async {
    try {
      final goals = await remoteDataSource.getMemberGoals(
        memberId: memberId,
        status: status,
        goalType: goalType,
      );
      return Right(goals);
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message));
    } on NetworkException {
      return const Left(NetworkFailure());
    } catch (e) {
      return Left(UnknownFailure(e.toString()));
    }
  }

  @override
  Future<Either<Failure, List<Goal>>> getFamilyGoals({
    required String familyId,
    String? status,
  }) async {
    try {
      final goals = await remoteDataSource.getFamilyGoals(
        familyId: familyId,
        status: status,
      );
      return Right(goals);
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message));
    } on NetworkException {
      return const Left(NetworkFailure());
    } catch (e) {
      return Left(UnknownFailure(e.toString()));
    }
  }

  @override
  Future<Either<Failure, Goal>> getGoal(String goalId) async {
    try {
      final goal = await remoteDataSource.getGoal(goalId);
      return Right(goal);
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message));
    } on NetworkException {
      return const Left(NetworkFailure());
    } catch (e) {
      return Left(UnknownFailure(e.toString()));
    }
  }

  @override
  Future<Either<Failure, Goal>> createGoal({
    required String memberId,
    required String goalType,
    required String description,
    required double targetValue,
    required String unit,
    required DateTime startDate,
    required DateTime endDate,
  }) async {
    try {
      final goal = await remoteDataSource.createGoal(
        memberId: memberId,
        goalType: goalType,
        description: description,
        targetValue: targetValue,
        unit: unit,
        startDate: startDate,
        endDate: endDate,
      );
      return Right(goal);
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message));
    } on NetworkException {
      return const Left(NetworkFailure());
    } catch (e) {
      return Left(UnknownFailure(e.toString()));
    }
  }

  @override
  Future<Either<Failure, Goal>> updateGoal({
    required String goalId,
    required String memberId,
    String? description,
    double? targetValue,
    DateTime? endDate,
    String? status,
  }) async {
    try {
      final goal = await remoteDataSource.updateGoal(
        goalId: goalId,
        memberId: memberId,
        description: description,
        targetValue: targetValue,
        endDate: endDate,
        status: status,
      );
      return Right(goal);
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message));
    } on NetworkException {
      return const Left(NetworkFailure());
    } catch (e) {
      return Left(UnknownFailure(e.toString()));
    }
  }

  @override
  Future<Either<Failure, void>> recordProgress({
    required String goalId,
    required String memberId,
    required double progressIncrement,
    String? notes,
    DateTime? recordDate,
  }) async {
    try {
      await remoteDataSource.recordProgress(
        goalId: goalId,
        memberId: memberId,
        progressIncrement: progressIncrement,
        notes: notes,
        recordDate: recordDate,
      );
      return const Right(null);
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message));
    } on NetworkException {
      return const Left(NetworkFailure());
    } catch (e) {
      return Left(UnknownFailure(e.toString()));
    }
  }

  @override
  Future<Either<Failure, WeeklySummary>> getWeeklySummary(String goalId) async {
    try {
      final summary = await remoteDataSource.getWeeklySummary(goalId);
      return Right(summary);
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message));
    } on NetworkException {
      return const Left(NetworkFailure());
    } catch (e) {
      return Left(UnknownFailure(e.toString()));
    }
  }
}
