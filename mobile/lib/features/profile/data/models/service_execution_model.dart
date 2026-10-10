import '../../domain/entities/service_execution.dart';

class ServiceExecutionModel extends ServiceExecution {
  const ServiceExecutionModel({
    required super.id,
    required super.jobName,
    required super.schedulerName,
    required super.status,
    required super.triggerType,
    super.startedAt,
    super.completedAt,
    super.durationMs,
    super.errorMessage,
    super.resultSummary,
    required super.createdAt,
  });

  factory ServiceExecutionModel.fromJson(Map<String, dynamic> json) {
    return ServiceExecutionModel(
      id: json['id'] as String,
      jobName: json['job_name'] as String,
      schedulerName: json['scheduler_name'] as String,
      status: _parseStatus(json['status'] as String),
      triggerType: json['trigger_type'] as String? ?? 'scheduled',
      startedAt: json['started_at'] != null
          ? DateTime.parse(json['started_at'] as String)
          : null,
      completedAt: json['completed_at'] != null
          ? DateTime.parse(json['completed_at'] as String)
          : null,
      durationMs: json['duration_ms'] as int?,
      errorMessage: json['error_message'] as String?,
      resultSummary: json['result_summary'] as Map<String, dynamic>?,
      createdAt: DateTime.parse(json['created_at'] as String),
    );
  }

  static ExecutionStatus _parseStatus(String status) {
    switch (status.toLowerCase()) {
      case 'pending':
        return ExecutionStatus.pending;
      case 'running':
        return ExecutionStatus.running;
      case 'completed':
        return ExecutionStatus.completed;
      case 'failed':
        return ExecutionStatus.failed;
      case 'timeout':
        return ExecutionStatus.timeout;
      case 'cancelled':
        return ExecutionStatus.cancelled;
      default:
        return ExecutionStatus.pending;
    }
  }
}

class ExecutionHistoryModel extends ExecutionHistory {
  const ExecutionHistoryModel({
    required super.executions,
    required super.total,
  });

  factory ExecutionHistoryModel.fromJson(Map<String, dynamic> json) {
    final items = json['items'] as List<dynamic>? ?? [];
    return ExecutionHistoryModel(
      executions: items
          .map((e) => ServiceExecutionModel.fromJson(e as Map<String, dynamic>))
          .toList(),
      total: json['total'] as int? ?? items.length,
    );
  }
}
