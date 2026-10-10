import '../../domain/entities/family_task.dart';

class FamilyTaskModel extends FamilyTask {
  const FamilyTaskModel({
    required super.id,
    required super.familyId,
    super.parentTaskId,
    required super.title,
    super.description,
    super.taskType,
    required super.creatorId,
    super.assigneeId,
    super.dueDate,
    super.dueTime,
    super.priority,
    super.status,
    super.completedAt,
    super.metadata,
    required super.createdAt,
    required super.updatedAt,
  });

  factory FamilyTaskModel.fromJson(Map<String, dynamic> json) {
    return FamilyTaskModel(
      id: json['id'] as String,
      familyId: (json['family_id'] as String?) ?? '',
      parentTaskId: json['parent_task_id'] as String?,
      title: json['title'] as String? ?? '',
      description: json['description'] as String?,
      taskType: json['task_type'] as String?,
      creatorId: (json['creator_id'] as String?) ?? '',
      assigneeId: json['assignee_id'] as String?,
      dueDate: json['due_date'] != null ? DateTime.parse(json['due_date'] as String) : null,
      dueTime: json['due_time'] != null ? _parseTime(json['due_time'] as String) : null,
      priority: _parsePriority(json['priority'] as String?),
      status: _parseStatus(json['status'] as String?),
      completedAt: json['completed_at'] != null ? DateTime.parse(json['completed_at'] as String) : null,
      metadata: json['metadata'] as Map<String, dynamic>?,
      createdAt: json['created_at'] != null ? DateTime.parse(json['created_at'] as String) : DateTime.now(),
      updatedAt: json['updated_at'] != null ? DateTime.parse(json['updated_at'] as String) : DateTime.now(),
    );
  }

  static DateTime _parseTime(String timeStr) {
    final parts = timeStr.split(':');
    final now = DateTime.now();
    return DateTime(
      now.year,
      now.month,
      now.day,
      int.parse(parts[0]),
      int.parse(parts[1]),
      parts.length > 2 ? int.parse(parts[2].split('.')[0]) : 0,
    );
  }

  static TaskPriority _parsePriority(String? priority) {
    switch (priority) {
      case 'low':
        return TaskPriority.low;
      case 'high':
        return TaskPriority.high;
      case 'urgent':
        return TaskPriority.urgent;
      default:
        return TaskPriority.normal;
    }
  }

  static TaskStatus _parseStatus(String? status) {
    switch (status) {
      case 'in_progress':
        return TaskStatus.inProgress;
      case 'completed':
        return TaskStatus.completed;
      case 'cancelled':
        return TaskStatus.cancelled;
      default:
        return TaskStatus.pending;
    }
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'family_id': familyId,
      'parent_task_id': parentTaskId,
      'title': title,
      'description': description,
      'task_type': taskType,
      'creator_id': creatorId,
      'assignee_id': assigneeId,
      'due_date': dueDate?.toIso8601String().split('T')[0],
      'due_time': dueTime != null
          ? '${dueTime!.hour.toString().padLeft(2, '0')}:${dueTime!.minute.toString().padLeft(2, '0')}'
          : null,
      'priority': priority.name,
      'status': status == TaskStatus.inProgress ? 'in_progress' : status.name,
      'completed_at': completedAt?.toIso8601String(),
      'metadata': metadata,
      'created_at': createdAt.toIso8601String(),
      'updated_at': updatedAt.toIso8601String(),
    };
  }
}
