import 'package:dartz/dartz.dart';
import '../../../../core/error/failures.dart';
import '../entities/goal.dart';

/// Goals repository interface
abstract class GoalsRepository {
  /// Get goals for a member
  Future<Either<Failure, List<Goal>>> getMemberGoals({
    required String memberId,
    String? status,
    String? goalType,
  });

  /// Get goals for a family
  Future<Either<Failure, List<Goal>>> getFamilyGoals({
    required String familyId,
    String? status,
  });

  /// Get a single goal by ID
  Future<Either<Failure, Goal>> getGoal(String goalId);

  /// Create a new goal
  Future<Either<Failure, Goal>> createGoal({
    required String memberId,
    required String goalType,
    required String description,
    required double targetValue,
    required String unit,
    required DateTime startDate,
    required DateTime endDate,
  });

  /// Update a goal
  Future<Either<Failure, Goal>> updateGoal({
    required String goalId,
    required String memberId,
    String? description,
    double? targetValue,
    DateTime? endDate,
    String? status,
  });

  /// Record progress for a goal
  Future<Either<Failure, void>> recordProgress({
    required String goalId,
    required String memberId,
    required double progressIncrement,
    String? notes,
    DateTime? recordDate,
  });

  /// Get weekly summary for a goal
  Future<Either<Failure, WeeklySummary>> getWeeklySummary(String goalId);
}
