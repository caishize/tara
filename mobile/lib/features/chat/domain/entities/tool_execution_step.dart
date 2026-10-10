import 'package:equatable/equatable.dart';
import '../../domain/entities/chat_message.dart';

/// 🔴 工具执行信息 (用于streaming期间的状态管理)
class ToolExecutionStep extends Equatable {
  final String toolName;
  final String status;
  final DateTime timestamp;
  final Map<String, dynamic>? result;
  final String? executionId; // 🔴 For on-demand detail retrieval
  final Map<String, dynamic>? keyResults; // 🔴 Key results for expandable display
  final int? durationMs; // 🔴 Execution duration
  final String? summary; // 🔴 NEW: Human-readable summary from backend
  final Map<String, dynamic>? arguments; // 🔴 NEW: Tool call arguments
  final List<String> progressLog; // 🔴 NEW: Real-time progress messages for Cursor-style display

  const ToolExecutionStep({
    required this.toolName,
    required this.status,
    required this.timestamp,
    this.result,
    this.executionId,
    this.keyResults,
    this.durationMs,
    this.summary,
    this.arguments,
    this.progressLog = const [],
  });

  /// Convert to ToolExecution entity for ChatMessage
  ToolExecution toEntity() {
    return ToolExecution(
      toolName: toolName,
      status: status,
      timestamp: timestamp,
      result: result,
      executionId: executionId,
      keyResults: keyResults,
      durationMs: durationMs,
      // 🔴 FIX: Pass summary to entity
      summary: summary,
      // 🔴 FIX: Pass arguments to entity for expansion during streaming
      arguments: arguments,
    );
  }

  ToolExecutionStep copyWith({
    String? toolName,
    String? status,
    DateTime? timestamp,
    Map<String, dynamic>? result,
    String? executionId,
    Map<String, dynamic>? keyResults,
    int? durationMs,
    String? summary,
    Map<String, dynamic>? arguments,
    List<String>? progressLog,
  }) {
    return ToolExecutionStep(
      toolName: toolName ?? this.toolName,
      status: status ?? this.status,
      timestamp: timestamp ?? this.timestamp,
      result: result ?? this.result,
      executionId: executionId ?? this.executionId,
      keyResults: keyResults ?? this.keyResults,
      durationMs: durationMs ?? this.durationMs,
      summary: summary ?? this.summary,
      arguments: arguments ?? this.arguments,
      progressLog: progressLog ?? this.progressLog,
    );
  }

  @override
  List<Object?> get props => [
    toolName,
    status,
    timestamp,
    result,
    executionId,
    keyResults,
    durationMs,
    summary,
    arguments,
    progressLog,
  ];
}
