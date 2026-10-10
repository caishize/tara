import 'package:equatable/equatable.dart';

/// Status of a job execution
enum ExecutionStatus {
  pending,
  running,
  completed,
  failed,
  timeout,
  cancelled,
}

/// A single service execution record
class ServiceExecution extends Equatable {
  final String id;
  final String jobName;
  final String schedulerName;
  final ExecutionStatus status;
  final String triggerType;
  final DateTime? startedAt;
  final DateTime? completedAt;
  final int? durationMs;
  final String? errorMessage;
  final Map<String, dynamic>? resultSummary;
  final DateTime createdAt;

  const ServiceExecution({
    required this.id,
    required this.jobName,
    required this.schedulerName,
    required this.status,
    required this.triggerType,
    this.startedAt,
    this.completedAt,
    this.durationMs,
    this.errorMessage,
    this.resultSummary,
    required this.createdAt,
  });

  /// Check if execution was successful
  bool get isSuccess => status == ExecutionStatus.completed;

  /// Check if execution failed
  bool get isFailed =>
      status == ExecutionStatus.failed ||
      status == ExecutionStatus.timeout ||
      status == ExecutionStatus.cancelled;

  /// Get status display text
  String get statusText {
    switch (status) {
      case ExecutionStatus.pending:
        return '等待中';
      case ExecutionStatus.running:
        return '执行中';
      case ExecutionStatus.completed:
        return '执行成功';
      case ExecutionStatus.failed:
        return '执行失败';
      case ExecutionStatus.timeout:
        return '执行超时';
      case ExecutionStatus.cancelled:
        return '已取消';
    }
  }

  /// Get duration text
  String? get durationText {
    if (durationMs == null) return null;
    if (durationMs! < 1000) return '${durationMs}ms';
    if (durationMs! < 60000) return '${(durationMs! / 1000).toStringAsFixed(1)}秒';
    return '${(durationMs! / 60000).toStringAsFixed(1)}分钟';
  }

  /// Get relative time text
  String get relativeTimeText {
    final now = DateTime.now();
    final diff = now.difference(createdAt);

    if (diff.inMinutes < 1) return '刚刚';
    if (diff.inMinutes < 60) return '${diff.inMinutes}分钟前';
    if (diff.inHours < 24) return '${diff.inHours}小时前';
    if (diff.inDays < 7) return '${diff.inDays}天前';
    return '${createdAt.month}月${createdAt.day}日';
  }

  /// Get result summary text
  String? get resultText {
    if (resultSummary == null) return null;
    // Try to extract meaningful info from result
    if (resultSummary!.containsKey('message')) {
      return resultSummary!['message'] as String?;
    }
    if (resultSummary!.containsKey('count')) {
      return '处理了 ${resultSummary!['count']} 条数据';
    }
    return null;
  }

  @override
  List<Object?> get props => [
        id,
        jobName,
        schedulerName,
        status,
        triggerType,
        startedAt,
        completedAt,
        durationMs,
        errorMessage,
        resultSummary,
        createdAt,
      ];
}

/// Execution history with pagination
class ExecutionHistory extends Equatable {
  final List<ServiceExecution> executions;
  final int total;

  const ExecutionHistory({
    required this.executions,
    required this.total,
  });

  factory ExecutionHistory.empty() => const ExecutionHistory(
        executions: [],
        total: 0,
      );

  @override
  List<Object?> get props => [executions, total];
}
