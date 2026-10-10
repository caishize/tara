import '../../domain/entities/goal.dart';

/// Goal model for API serialization
class GoalModel extends Goal {
  const GoalModel({
    required super.id,
    required super.memberId,
    required super.familyId,
    required super.goalType,
    required super.description,
    required super.targetValue,
    required super.unit,
    required super.startDate,
    required super.endDate,
    required super.currentProgress,
    required super.completionPercentage,
    required super.decomposition,
    required super.status,
    required super.createdAt,
    required super.updatedAt,
  });

  factory GoalModel.fromJson(Map<String, dynamic> json) {
    final decompositionJson = json['decomposition'] as Map<String, dynamic>? ?? {};

    return GoalModel(
      id: json['id'] as String? ?? '',
      memberId: json['member_id'] as String? ?? '',
      familyId: json['family_id'] as String? ?? '',
      goalType: json['goal_type'] as String? ?? '',
      description: json['description'] as String? ?? '',
      targetValue: _parseDouble(json['target_value']) ?? 0,
      unit: json['unit'] as String? ?? '',
      startDate: DateTime.parse(json['start_date'] as String),
      endDate: DateTime.parse(json['end_date'] as String),
      currentProgress: _parseDouble(json['current_progress']) ?? 0,
      completionPercentage: _parseDouble(json['completion_percentage']) ?? 0,
      decomposition: GoalDecomposition(
        monthly: _parseDouble(decompositionJson['monthly']) ?? 0,
        weekly: _parseDouble(decompositionJson['weekly']) ?? 0,
        daily: _parseDouble(decompositionJson['daily']) ?? 0,
      ),
      status: _parseStatus(json['status'] as String?),
      createdAt: DateTime.parse(json['created_at'] as String? ?? DateTime.now().toIso8601String()),
      updatedAt: DateTime.parse(json['updated_at'] as String? ?? DateTime.now().toIso8601String()),
    );
  }

  /// Parse a value that could be String or num to double
  static double? _parseDouble(dynamic value) {
    if (value == null) return null;
    if (value is num) return value.toDouble();
    if (value is String) return double.tryParse(value);
    return null;
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'member_id': memberId,
      'family_id': familyId,
      'goal_type': goalType,
      'description': description,
      'target_value': targetValue,
      'unit': unit,
      'start_date': startDate.toIso8601String().split('T').first,
      'end_date': endDate.toIso8601String().split('T').first,
      'current_progress': currentProgress,
      'completion_percentage': completionPercentage,
      'status': _statusToString(status),
    };
  }

  static GoalStatus _parseStatus(String? value) {
    return switch (value) {
      'active' => GoalStatus.active,
      'completed' => GoalStatus.completed,
      'abandoned' => GoalStatus.abandoned,
      'adjusted' => GoalStatus.adjusted,
      _ => GoalStatus.active,
    };
  }

  static String _statusToString(GoalStatus status) {
    return switch (status) {
      GoalStatus.active => 'active',
      GoalStatus.completed => 'completed',
      GoalStatus.abandoned => 'abandoned',
      GoalStatus.adjusted => 'adjusted',
    };
  }
}

/// Weekly summary model
class WeeklySummaryModel extends WeeklySummary {
  const WeeklySummaryModel({
    required super.goalId,
    required super.description,
    required super.weeklyTarget,
    required super.actualProgress,
    required super.status,
    required super.message,
  });

  factory WeeklySummaryModel.fromJson(Map<String, dynamic> json) {
    return WeeklySummaryModel(
      goalId: json['goal_id'] as String? ?? '',
      description: json['description'] as String? ?? '',
      weeklyTarget: _parseDouble(json['weekly_target']) ?? 0,
      actualProgress: _parseDouble(json['actual_progress']) ?? 0,
      status: json['status'] as String? ?? 'behind',
      message: json['message'] as String? ?? '',
    );
  }

  /// Parse a value that could be String or num to double
  static double? _parseDouble(dynamic value) {
    if (value == null) return null;
    if (value is num) return value.toDouble();
    if (value is String) return double.tryParse(value);
    return null;
  }
}
