import 'package:equatable/equatable.dart';

/// Task status
enum TaskStatus {
  pending,
  inProgress,
  completed,
  cancelled,
}

/// Task priority
enum TaskPriority {
  low,
  normal,
  high,
  urgent,
}

/// Family task entity
class FamilyTask extends Equatable {
  final String id;
  final String familyId;
  final String? parentTaskId;
  final String title;
  final String? description;
  final String? taskType;
  final String creatorId;
  final String? assigneeId;
  final DateTime? dueDate;
  final DateTime? dueTime;
  final TaskPriority priority;
  final TaskStatus status;
  final DateTime? completedAt;
  final Map<String, dynamic>? metadata;
  final DateTime createdAt;
  final DateTime updatedAt;

  const FamilyTask({
    required this.id,
    required this.familyId,
    this.parentTaskId,
    required this.title,
    this.description,
    this.taskType,
    required this.creatorId,
    this.assigneeId,
    this.dueDate,
    this.dueTime,
    this.priority = TaskPriority.normal,
    this.status = TaskStatus.pending,
    this.completedAt,
    this.metadata,
    required this.createdAt,
    required this.updatedAt,
  });

  /// Get due datetime combining date and time
  DateTime? get dueDateTime {
    if (dueDate == null) return null;
    if (dueTime != null) {
      return DateTime(
        dueDate!.year,
        dueDate!.month,
        dueDate!.day,
        dueTime!.hour,
        dueTime!.minute,
      );
    }
    return DateTime(dueDate!.year, dueDate!.month, dueDate!.day, 23, 59, 59);
  }

  /// Check if task is overdue
  bool get isOverdue {
    if (dueDate == null || status == TaskStatus.completed || status == TaskStatus.cancelled) {
      return false;
    }
    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);
    final taskDue = DateTime(dueDate!.year, dueDate!.month, dueDate!.day);
    if (taskDue.isBefore(today)) return true;
    if (taskDue.isAtSameMomentAs(today) && dueTime != null) {
      return now.isAfter(dueDateTime!);
    }
    return false;
  }

  @override
  List<Object?> get props => [
        id,
        familyId,
        parentTaskId,
        title,
        description,
        taskType,
        creatorId,
        assigneeId,
        dueDate,
        dueTime,
        priority,
        status,
        completedAt,
        metadata,
        createdAt,
        updatedAt,
      ];
}
