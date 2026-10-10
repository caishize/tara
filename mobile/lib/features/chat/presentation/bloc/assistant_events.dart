import 'dart:typed_data';
import 'package:equatable/equatable.dart';
import '../../domain/entities/chat_message.dart';
import '../../data/datasources/assistant_remote_datasource.dart';

// Events
abstract class AssistantEvent extends Equatable {
  const AssistantEvent();
  @override
  List<Object?> get props => [];
}

/// Route info received from stream bootstrap events (dual-brain routing decision)
class AssistantRouteInfoReceived extends AssistantEvent {
  final String routeType; // fast, slow, hybrid
  const AssistantRouteInfoReceived(this.routeType);
  @override
  List<Object?> get props => [routeType];
}

/// Slow path result received via WebSocket
class AssistantSlowPathResultReceived extends AssistantEvent {
  final StreamEvent event;
  const AssistantSlowPathResultReceived(this.event);
  @override
  List<Object?> get props => [event];
}

/// Task queued for slow path processing
class AssistantTaskQueued extends AssistantEvent {
  final String? jobId;
  const AssistantTaskQueued(this.jobId);
  @override
  List<Object?> get props => [jobId];
}

/// Background job started for hybrid path
class AssistantBackgroundJobStarted extends AssistantEvent {
  final String? jobId;
  const AssistantBackgroundJobStarted(this.jobId);
  @override
  List<Object?> get props => [jobId];
}

class AssistantSendMessage extends AssistantEvent {
  final String message;

  const AssistantSendMessage(this.message);

  @override
  List<Object?> get props => [message];
}

class AssistantStreamMessage extends AssistantEvent {
  final String message;

  const AssistantStreamMessage(this.message);

  @override
  List<Object?> get props => [message];
}

/// Internal: dispatch a previously queued user message.
class AssistantDispatchQueuedMessage extends AssistantEvent {
  final String message;

  const AssistantDispatchQueuedMessage(this.message);

  @override
  List<Object?> get props => [message];
}

/// Voice message -- upload audio file, receive transcription + chat stream events
class AssistantVoiceMessage extends AssistantEvent {
  final String audioPath;

  const AssistantVoiceMessage(this.audioPath);

  @override
  List<Object?> get props => [audioPath];
}

/// Internal: transcription text received during voice flow
class VoiceTranscriptionReceived extends AssistantEvent {
  final String text;
  const VoiceTranscriptionReceived(this.text);
  @override
  List<Object?> get props => [text];
}

/// Voice streaming events (PLAN-009)
class VoiceStreamStartRequested extends AssistantEvent {
  const VoiceStreamStartRequested();
  @override
  List<Object?> get props => [];
}

class VoiceStreamChunkReady extends AssistantEvent {
  final Uint8List audioBytes;
  const VoiceStreamChunkReady(this.audioBytes);
  // M-2: Every audio chunk is unique — skip deep equality to prevent dedup
  @override
  List<Object?> get props => const [];
}

class VoiceStreamEndRequested extends AssistantEvent {
  const VoiceStreamEndRequested();
  @override
  List<Object?> get props => [];
}

class VoiceStreamCancelRequested extends AssistantEvent {
  const VoiceStreamCancelRequested();
  @override
  List<Object?> get props => [];
}

class VoiceStreamTranscriptionReceived extends AssistantEvent {
  final String text;
  final bool isPartial;
  final bool isCancelled;
  const VoiceStreamTranscriptionReceived({
    required this.text,
    required this.isPartial,
    this.isCancelled = false,
  });
  @override
  List<Object?> get props => [text, isPartial, isCancelled];
}

/// Memory extraction notification (PLAN-012)
class MemoryExtractedReceived extends AssistantEvent {
  final String summary;
  final Map<String, dynamic> entities;
  final List<String> mentionedPersons;
  const MemoryExtractedReceived({
    required this.summary,
    this.entities = const {},
    this.mentionedPersons = const [],
  });
  @override
  List<Object?> get props => [summary, entities, mentionedPersons];
}

class AssistantStreamChunkReceived extends AssistantEvent {
  final String chunk;

  const AssistantStreamChunkReceived(this.chunk);

  @override
  List<Object?> get props => [chunk];
}

class AssistantStreamCompleted extends AssistantEvent {
  final List<QuickAction>? quickActions;
  final String? messageId;
  final String? intent;
  final Map<String, dynamic>? data;
  final List<Map<String, dynamic>>? progressHistory;
  final List<Map<String, dynamic>>? toolExecutions;
  final int? agenticIterations;
  final String? content;
  final String? cardType;
  final bool clearActiveJobId;

  const AssistantStreamCompleted({
    this.quickActions,
    this.messageId,
    this.intent,
    this.data,
    this.progressHistory,
    this.toolExecutions,
    this.agenticIterations,
    this.content,
    this.cardType,
    this.clearActiveJobId = false,
  });

  @override
  List<Object?> get props => [
        quickActions,
        messageId,
        intent,
        data,
        progressHistory,
        toolExecutions,
        agenticIterations,
        content,
        cardType,
        clearActiveJobId
      ];
}

class AssistantStreamToolExecutionReceived extends AssistantEvent {
  final String toolName;
  final String status;
  final Map<String, dynamic>? result;
  final String? executionId;
  final Map<String, dynamic>? keyResults;
  final int? durationMs;
  final String? summary;
  final Map<String, dynamic>? arguments;

  const AssistantStreamToolExecutionReceived({
    required this.toolName,
    required this.status,
    this.result,
    this.executionId,
    this.keyResults,
    this.durationMs,
    this.summary,
    this.arguments,
  });

  @override
  List<Object?> get props => [
        toolName,
        status,
        result,
        executionId,
        keyResults,
        durationMs,
        summary,
        arguments
      ];
}

class AssistantStreamConfirmCardReceived extends AssistantEvent {
  final Map<String, dynamic> payload;

  const AssistantStreamConfirmCardReceived(this.payload);

  @override
  List<Object?> get props => [payload];
}

class AssistantStreamAskUserQuestionReceived extends AssistantEvent {
  final Map<String, dynamic> payload;

  const AssistantStreamAskUserQuestionReceived(this.payload);

  @override
  List<Object?> get props => [payload];
}

class AssistantStreamSessionReceived extends AssistantEvent {
  final String sessionId;

  const AssistantStreamSessionReceived(this.sessionId);

  @override
  List<Object?> get props => [sessionId];
}

class AssistantStreamProgressReceived extends AssistantEvent {
  final String stage;
  final String message;

  const AssistantStreamProgressReceived(this.stage, this.message);

  @override
  List<Object?> get props => [stage, message];
}

/// Route tool_progress events into the matching ToolStep's progressLog
class AssistantStreamToolProgressReceived extends AssistantEvent {
  final String toolName;
  final String message;

  const AssistantStreamToolProgressReceived({
    required this.toolName,
    required this.message,
  });

  @override
  List<Object?> get props => [toolName, message];
}

class AssistantStreamThinkingReceived extends AssistantEvent {
  final String thinking;

  const AssistantStreamThinkingReceived(this.thinking);

  @override
  List<Object?> get props => [thinking];
}

class AssistantStreamThinkingStarted extends AssistantEvent {
  final String content;

  const AssistantStreamThinkingStarted({this.content = ''});

  @override
  List<Object?> get props => [content];
}

class AssistantStreamErrorReceived extends AssistantEvent {
  final String error;

  const AssistantStreamErrorReceived(this.error);

  @override
  List<Object?> get props => [error];
}

class AssistantRestoreSession extends AssistantEvent {
  const AssistantRestoreSession();

  @override
  List<Object?> get props => [];
}

class AssistantLoadHistory extends AssistantEvent {
  final String sessionId;

  const AssistantLoadHistory(this.sessionId);

  @override
  List<Object?> get props => [sessionId];
}

class LoadMoreHistoryRequested extends AssistantEvent {
  const LoadMoreHistoryRequested();

  @override
  List<Object?> get props => [];
}

class AssistantClearChat extends AssistantEvent {
  const AssistantClearChat();
}

class AssistantLoadQuickActions extends AssistantEvent {
  const AssistantLoadQuickActions();
}

class AssistantQuickActionTapped extends AssistantEvent {
  final QuickAction action;

  const AssistantQuickActionTapped(this.action);

  @override
  List<Object?> get props => [action];
}

class AssistantRegenerateMessage extends AssistantEvent {
  final String messageId;

  const AssistantRegenerateMessage(this.messageId);

  @override
  List<Object?> get props => [messageId];
}

class AssistantEditMessage extends AssistantEvent {
  final String messageId;
  final String newContent;

  const AssistantEditMessage(this.messageId, this.newContent);

  @override
  List<Object?> get props => [messageId, newContent];
}

class AssistantDismissSuggestion extends AssistantEvent {
  final String suggestionId;

  const AssistantDismissSuggestion(this.suggestionId);

  @override
  List<Object?> get props => [suggestionId];
}

class AssistantActOnSuggestion extends AssistantEvent {
  final String suggestionId;

  const AssistantActOnSuggestion(this.suggestionId);

  @override
  List<Object?> get props => [suggestionId];
}

class AssistantAssignTask extends AssistantEvent {
  final String taskId;
  final String assigneeId;

  const AssistantAssignTask(this.taskId, this.assigneeId);

  @override
  List<Object?> get props => [taskId, assigneeId];
}

class AssistantConfirmTravelPlan extends AssistantEvent {
  final String messageId;
  final Map<String, dynamic> planData;
  final void Function(String? planId)? onComplete;

  const AssistantConfirmTravelPlan(
    this.messageId,
    this.planData, {
    this.onComplete,
  });

  @override
  List<Object?> get props => [messageId, planData];
}

/// Sync any pending actions missed while offline (reconnect compensation).
class AssistantSyncPendingActions extends AssistantEvent {
  const AssistantSyncPendingActions();
}

/// User pressed stop button to cancel ongoing generation.
class AssistantStopGeneration extends AssistantEvent {
  const AssistantStopGeneration();
}

/// User submitted feedback (thumbs up/down) on a message.
class AssistantFeedbackSubmitted extends AssistantEvent {
  final String messageId;
  final bool isPositive;
  final String? reason;

  const AssistantFeedbackSubmitted({
    required this.messageId,
    required this.isPositive,
    this.reason,
  });

  @override
  List<Object?> get props => [messageId, isPositive, reason];
}

/// Full-duplex: partial content received (may be replaced on correction)
class AssistantPartialContentReceived extends AssistantEvent {
  /// The full partial text accumulated so far (not a delta).
  /// Named 'chunk' for consistency with StreamEvent but contains complete text.
  final String chunk;
  final String? generationId;
  final String? interruptedBy;

  const AssistantPartialContentReceived({
    required this.chunk,
    this.generationId,
    this.interruptedBy,
  });

  @override
  List<Object?> get props => [chunk, generationId, interruptedBy];
}

/// Full-duplex: bridging event (correction replaces partial, digression adds new bubble)
class AssistantBridgingReceived extends AssistantEvent {
  final String bridgingType; // "correction" | "digression"
  final String? generationId;

  const AssistantBridgingReceived({
    required this.bridgingType,
    this.generationId,
  });

  @override
  List<Object?> get props => [bridgingType, generationId];
}

/// Full-duplex: generation state change (interrupt/resume/cancel)
class AssistantGenerationStateReceived extends AssistantEvent {
  final String action; // "interrupt" | "resume" | "cancel"
  final String? generationId;

  const AssistantGenerationStateReceived({
    required this.action,
    this.generationId,
  });

  @override
  List<Object?> get props => [action, generationId];
}

/// Full-duplex: sidekick insight card received
class AssistantSidekickInsightReceived extends AssistantEvent {
  final Map<String, dynamic> payload;

  const AssistantSidekickInsightReceived(this.payload);

  @override
  List<Object?> get props => [payload];
}

/// Full-duplex: signal accepted hint (auto-dismiss after 2s)
class AssistantSignalHintReceived extends AssistantEvent {
  final String hint;
  final String? signalType;

  const AssistantSignalHintReceived(this.hint, {this.signalType});

  @override
  List<Object?> get props => [hint, signalType];
}

/// Full-duplex: dismiss signal hint
class AssistantSignalHintDismissed extends AssistantEvent {
  const AssistantSignalHintDismissed();
}
