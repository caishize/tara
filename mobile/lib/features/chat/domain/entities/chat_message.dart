import 'package:equatable/equatable.dart';
import 'generation_step.dart';

enum MessageRole { user, assistant }

/// Represents a progress step during message processing
class MessageProgressStep extends Equatable {
  final String stage;
  final String message;
  final DateTime timestamp;
  final Map<String, dynamic>? data;

  const MessageProgressStep({
    required this.stage,
    required this.message,
    required this.timestamp,
    this.data,
  });

  factory MessageProgressStep.fromJson(Map<String, dynamic> json) {
    return MessageProgressStep(
      stage: json['stage'] as String? ?? '',
      message: json['message'] as String? ?? '',
      timestamp: json['timestamp'] != null
          ? DateTime.parse(json['timestamp'] as String)
          : DateTime.now(),
      data: json['data'] as Map<String, dynamic>?,
    );
  }

  @override
  List<Object?> get props => [stage, message, timestamp, data];
}

/// Represents a tool execution event
class ToolExecution extends Equatable {
  final String toolName;
  final String status; // 'start', 'success', 'error'
  final DateTime timestamp;
  final Map<String, dynamic>? result;
  final String? executionId; // 🔴 For on-demand detail retrieval
  final Map<String, dynamic>? keyResults; // 🔴 Key results for expandable display
  final int? durationMs; // 🔴 Execution duration in milliseconds
  final String? _summary; // 🔴 NEW: Explicit summary field (top-level from backend)
  final Map<String, dynamic>? arguments; // 🔴 Tool call arguments (for expansion during streaming)

  const ToolExecution({
    required this.toolName,
    required this.status,
    required this.timestamp,
    this.result,
    this.executionId,
    this.keyResults,
    this.durationMs,
    String? summary,
    this.arguments,
  }) : _summary = summary;

  factory ToolExecution.fromJson(Map<String, dynamic> json) {
    return ToolExecution(
      toolName: json['tool_name'] as String? ?? '',
      status: json['status'] as String? ?? '',
      timestamp: json['timestamp'] != null
          ? DateTime.parse(json['timestamp'] as String)
          : DateTime.now(),
      result: json['result'] as Map<String, dynamic>?,
      executionId: json['execution_id'] as String?,
      keyResults: json['key_results'] as Map<String, dynamic>?,
      durationMs: json['duration_ms'] as int?,
      // 🔴 FIX: Extract summary from top-level field (backend sends it there)
      summary: json['summary'] as String?,
      arguments: json['arguments'] as Map<String, dynamic>?,
    );
  }

  /// Get human-readable summary
  /// 🔴 FIX: Type-safe extraction with proper null and type checks
  String? get summary {
    if (_summary != null) return _summary;
    final resultSummary = result?['summary'];
    if (resultSummary is String) return resultSummary;
    return null;
  }

  /// Get formatted duration string
  String? get durationFormatted {
    if (durationMs == null) return null;
    if (durationMs! < 1000) return '${durationMs}ms';
    return '${(durationMs! / 1000).toStringAsFixed(1)}s';
  }

  @override
  List<Object?> get props => [toolName, status, timestamp, result, executionId, keyResults, durationMs, _summary, arguments];
}

class ChatMessage extends Equatable {
  final String id;
  final String sessionId;
  final MessageRole role;
  final String content;
  final String? thinking; // AI思考过程
  final String? intent;
  final Map<String, dynamic>? data;
  final List<QuickAction>? quickActions;
  final List<MessageProgressStep>? progressHistory; // 处理进度历史
  final List<ToolExecution>? toolExecutions; // 工具执行记录 (Deprecating in favor of generationSteps)
  final List<GenerationStep>? generationSteps; // 🔴 NEW: Sequential steps
  final bool isStreaming;
  final bool isStopped; // User stopped generation
  final bool isSuperseded; // Message was regenerated (replaced by newer version)
  final bool isPartial; // Full-duplex: content is partial (may be replaced on correction)
  final String? signalType; // Full-duplex: "correction" | "cancel" | null — how partial ended
  final String? generationId; // Full-duplex: generation-level correlation identifier
  final String? continuesFrom; // Full-duplex: links to the generationId this message continues from
  final String? asyncSource; // "briefing" | "discovery" | "reminder" — async push origin
  final String? cardType; // Explicit card type from done event (e.g. 'event', 'travel', 'gift')
  final String? feedback; // "positive" | "negative" | null
  final String? feedbackReason; // Reason for negative feedback
  final DateTime createdAt;

  const ChatMessage({
    required this.id,
    required this.sessionId,
    required this.role,
    required this.content,
    this.thinking,
    this.intent,
    this.data,
    this.quickActions,
    this.progressHistory,
    this.toolExecutions,
    this.generationSteps,
    this.isStreaming = false,
    this.isStopped = false,
    this.isSuperseded = false,
    this.isPartial = false,
    this.signalType,
    this.generationId,
    this.continuesFrom,
    this.asyncSource,
    this.cardType,
    this.feedback,
    this.feedbackReason,
    required this.createdAt,
  });

  ChatMessage copyWith({
    String? id,
    String? sessionId,
    MessageRole? role,
    String? content,
    String? thinking,
    String? intent,
    Map<String, dynamic>? data,
    List<QuickAction>? quickActions,
    List<MessageProgressStep>? progressHistory,
    List<ToolExecution>? toolExecutions,
    List<GenerationStep>? generationSteps,
    bool? isStreaming,
    bool? isStopped,
    bool? isSuperseded,
    bool? isPartial,
    String? signalType,
    bool clearSignalType = false,
    String? generationId,
    bool clearGenerationId = false,
    String? continuesFrom,
    bool clearContinuesFrom = false,
    String? asyncSource,
    String? cardType,
    String? feedback,
    String? feedbackReason,
    DateTime? createdAt,
  }) {
    return ChatMessage(
      id: id ?? this.id,
      sessionId: sessionId ?? this.sessionId,
      role: role ?? this.role,
      content: content ?? this.content,
      thinking: thinking ?? this.thinking,
      intent: intent ?? this.intent,
      data: data ?? this.data,
      quickActions: quickActions ?? this.quickActions,
      progressHistory: progressHistory ?? this.progressHistory,
      toolExecutions: toolExecutions ?? this.toolExecutions,
      generationSteps: generationSteps ?? this.generationSteps,
      isStreaming: isStreaming ?? this.isStreaming,
      isStopped: isStopped ?? this.isStopped,
      isSuperseded: isSuperseded ?? this.isSuperseded,
      isPartial: isPartial ?? this.isPartial,
      signalType: clearSignalType ? null : (signalType ?? this.signalType),
      generationId: clearGenerationId ? null : (generationId ?? this.generationId),
      continuesFrom: clearContinuesFrom ? null : (continuesFrom ?? this.continuesFrom),
      asyncSource: asyncSource ?? this.asyncSource,
      cardType: cardType ?? this.cardType,
      feedback: feedback ?? this.feedback,
      feedbackReason: feedbackReason ?? this.feedbackReason,
      createdAt: createdAt ?? this.createdAt,
    );
  }

  @override
  List<Object?> get props => [id, sessionId, role, content, thinking, intent, data, quickActions, progressHistory, toolExecutions, generationSteps, isStreaming, isStopped, isSuperseded, isPartial, signalType, generationId, continuesFrom, asyncSource, cardType, feedback, feedbackReason, createdAt];
}

class QuickAction extends Equatable {
  final String label;
  final String action;
  final String? type; // 'message' | 'navigate' | 'tool' | 'link'
  final String? icon;
  final String? variant; // 'default' | 'primary' | 'secondary' | 'destructive'
  final Map<String, dynamic>? metadata; // entity IDs: {trip_id, event_id, member_id, ...}

  const QuickAction({
    required this.label,
    required this.action,
    this.type,
    this.icon,
    this.variant,
    this.metadata,
  });

  @override
  List<Object?> get props => [label, action, type, icon, variant, metadata];
}

/// Chat response with multi-turn conversation support
class ChatResponse extends Equatable {
  final String sessionId;
  final String response;
  final String? intent;
  final Map<String, dynamic>? data;
  final List<QuickAction>? quickActions;
  final bool requiresMoreInfo;
  final Map<String, dynamic>? collectedInfo;

  const ChatResponse({
    required this.sessionId,
    required this.response,
    this.intent,
    this.data,
    this.quickActions,
    this.requiresMoreInfo = false,
    this.collectedInfo,
  });

  @override
  List<Object?> get props => [
        sessionId,
        response,
        intent,
        data,
        quickActions,
        requiresMoreInfo,
        collectedInfo,
      ];
}

class ChatSession extends Equatable {
  final String id;
  final String? title;
  final DateTime createdAt;
  final DateTime? lastMessageAt;

  const ChatSession({
    required this.id,
    this.title,
    required this.createdAt,
    this.lastMessageAt,
  });

  @override
  List<Object?> get props => [id, title, createdAt, lastMessageAt];
}
