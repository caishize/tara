import 'package:equatable/equatable.dart';

/// Goal status enumeration
enum GoalStatus {
  active,
  completed,
  abandoned,
  adjusted,
}

/// Goal decomposition breakdown
class GoalDecomposition extends Equatable {
  final double monthly;
  final double weekly;
  final double daily;

  const GoalDecomposition({
    required this.monthly,
    required this.weekly,
    required this.daily,
  });

  @override
  List<Object?> get props => [monthly, weekly, daily];
}

/// Goal entity
class Goal extends Equatable {
  final String id;
  final String memberId;
  final String familyId;
  final String goalType;
  final String description;
  final double targetValue;
  final String unit;
  final DateTime startDate;
  final DateTime endDate;
  final double currentProgress;
  final double completionPercentage;
  final GoalDecomposition decomposition;
  final GoalStatus status;
  final DateTime createdAt;
  final DateTime updatedAt;

  const Goal({
    required this.id,
    required this.memberId,
    required this.familyId,
    required this.goalType,
    required this.description,
    required this.targetValue,
    required this.unit,
    required this.startDate,
    required this.endDate,
    required this.currentProgress,
    required this.completionPercentage,
    required this.decomposition,
    required this.status,
    required this.createdAt,
    required this.updatedAt,
  });

  /// Check if goal is on track based on decomposition
  bool get isOnTrack {
    final daysPassed = DateTime.now().difference(startDate).inDays;
    final expectedProgress = decomposition.daily * daysPassed;
    return currentProgress >= expectedProgress * 0.9; // 90% threshold
  }

  /// Get days remaining until deadline
  int get daysRemaining => endDate.difference(DateTime.now()).inDays;

  /// Get remaining value to achieve
  double get remainingValue => targetValue - currentProgress;

  /// Display formatted progress
  String get progressDisplay => '${currentProgress.toStringAsFixed(1)} / ${targetValue.toStringAsFixed(1)} $unit';

  /// Display formatted completion percentage
  String get completionDisplay => '${completionPercentage.toStringAsFixed(1)}%';

  /// Get goal type display name
  String get goalTypeDisplay {
    return switch (goalType) {
      'reading' => '阅读',
      'exercise' => '运动',
      'savings' => '储蓄',
      'learning' => '学习',
      'weight' => '体重',
      'sleep' => '睡眠',
      'meditation' => '冥想',
      'work' => '工作',
      _ => goalType,
    };
  }

  /// Get status display name
  String get statusDisplay {
    return switch (status) {
      GoalStatus.active => '进行中',
      GoalStatus.completed => '已完成',
      GoalStatus.abandoned => '已放弃',
      GoalStatus.adjusted => '已调整',
    };
  }

  @override
  List<Object?> get props => [
    id, memberId, familyId, goalType, description, targetValue, unit,
    startDate, endDate, currentProgress, completionPercentage,
    decomposition, status, createdAt, updatedAt,
  ];
}

/// Goal progress record
class GoalProgress extends Equatable {
  final String id;
  final String goalId;
  final String memberId;
  final DateTime recordDate;
  final double progressIncrement;
  final double cumulativeProgress;
  final String? notes;
  final DateTime createdAt;

  const GoalProgress({
    required this.id,
    required this.goalId,
    required this.memberId,
    required this.recordDate,
    required this.progressIncrement,
    required this.cumulativeProgress,
    this.notes,
    required this.createdAt,
  });

  @override
  List<Object?> get props => [
    id, goalId, memberId, recordDate, progressIncrement, cumulativeProgress, notes, createdAt,
  ];
}

/// Weekly summary
class WeeklySummary extends Equatable {
  final String goalId;
  final String description;
  final double weeklyTarget;
  final double actualProgress;
  final String status; // "exceeded", "on_track", "behind"
  final String message;

  const WeeklySummary({
    required this.goalId,
    required this.description,
    required this.weeklyTarget,
    required this.actualProgress,
    required this.status,
    required this.message,
  });

  bool get isOnTrack => status == 'on_track' || status == 'exceeded';

  @override
  List<Object?> get props => [goalId, description, weeklyTarget, actualProgress, status, message];
}
