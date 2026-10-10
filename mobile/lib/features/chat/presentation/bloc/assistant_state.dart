import 'package:equatable/equatable.dart';
import '../../domain/entities/chat_message.dart';
import '../../domain/entities/generation_step.dart';

// States
abstract class AssistantState extends Equatable {
  const AssistantState();
  @override
  List<Object?> get props => [];
}

class AssistantInitial extends AssistantState {
  const AssistantInitial();
}

/// Progress step info
class ProgressStep {
  final String stage;
  final String message;
  final DateTime timestamp;
  final Map<String, dynamic>? data;

  const ProgressStep({
    required this.stage,
    required this.message,
    required this.timestamp,
    this.data,
  });

  factory ProgressStep.fromJson(Map<String, dynamic> json) {
    return ProgressStep(
      stage: json['stage'] as String? ?? '',
      message: json['message'] as String? ?? '',
      timestamp: json['timestamp'] != null
          ? DateTime.parse(json['timestamp'] as String)
          : DateTime.now(),
      data: json['data'] as Map<String, dynamic>?,
    );
  }
}

class AssistantLoaded extends AssistantState {
  final List<ChatMessage> messages;
  final String? sessionId;
  final bool isLoading;
  final bool isStreaming;
  final int queuedInputCount;
  final String streamingContent;
  final List<QuickAction> quickActions;
  final String? error;
  final String? progressStage;
  final String? progressMessage;
  final List<ProgressStep> progressHistory;
  final List<GenerationStep> generationSteps;
  final String? activeJobId;
  /// Full-duplex: tracks the current generation ID for partial content
  final String? currentGenerationId;
  /// Full-duplex: true when the current streaming message is partial (may be replaced)
  final bool hasPartialMessage;
  /// Full-duplex: the type of interruption in progress ("correction" | "digression")
  final String? interruptionType;
  /// Full-duplex: true when a bridging event is expected (prevents queued dispatch race)
  final bool awaitingBridging;
  /// Full-duplex: signal hint text to show above input (auto-dismiss)
  final String? signalHint;
  /// Full-duplex: signal type for the current hint (drives color/icon)
  final String? signalHintType;
  /// Voice streaming: true when actively streaming audio to backend
  final bool isVoiceStreaming;
  /// Voice streaming: latest partial transcription text from ASR
  final String? partialTranscription;
  /// Voice streaming: current audio amplitude for waveform display (0.0-1.0)
  final double voiceAmplitude;
  /// Memory extraction: transient toast message (auto-dismiss)
  final String? memoryExtractedToast;
  /// History lazy-loading: true if there are more messages to load
  final bool historyHasMore;
  /// History lazy-loading: true while fetching older messages
  final bool isLoadingHistory;
  /// History lazy-loading: ID of the oldest loaded message (pagination cursor)
  final String? oldestMessageId;

  const AssistantLoaded({
    this.messages = const [],
    this.sessionId,
    this.isLoading = false,
    this.isStreaming = false,
    this.queuedInputCount = 0,
    this.streamingContent = '',
    this.quickActions = const [],
    this.error,
    this.progressStage,
    this.progressMessage,
    this.progressHistory = const [],
    this.generationSteps = const [],
    this.activeJobId,
    this.currentGenerationId,
    this.hasPartialMessage = false,
    this.interruptionType,
    this.awaitingBridging = false,
    this.signalHint,
    this.signalHintType,
    this.isVoiceStreaming = false,
    this.partialTranscription,
    this.voiceAmplitude = 0.0,
    this.memoryExtractedToast,
    this.historyHasMore = false,
    this.isLoadingHistory = false,
    this.oldestMessageId,
  });

  AssistantLoaded copyWith({
    List<ChatMessage>? messages,
    String? sessionId,
    bool? isLoading,
    bool? isStreaming,
    int? queuedInputCount,
    String? streamingContent,
    List<QuickAction>? quickActions,
    String? error,
    String? progressStage,
    String? progressMessage,
    List<ProgressStep>? progressHistory,
    List<GenerationStep>? generationSteps,
    String? activeJobId,
    bool clearActiveJobId = false,
    String? currentGenerationId,
    bool clearCurrentGenerationId = false,
    bool? hasPartialMessage,
    String? interruptionType,
    bool clearInterruptionType = false,
    bool? awaitingBridging,
    String? signalHint,
    bool clearSignalHint = false,
    String? signalHintType,
    bool clearSignalHintType = false,
    bool? isVoiceStreaming,
    String? partialTranscription,
    bool clearPartialTranscription = false,
    double? voiceAmplitude,
    String? memoryExtractedToast,
    bool clearMemoryExtractedToast = false,
    bool? historyHasMore,
    bool? isLoadingHistory,
    String? oldestMessageId,
    bool clearOldestMessageId = false,
  }) {
    return AssistantLoaded(
      messages: messages ?? this.messages,
      sessionId: sessionId ?? this.sessionId,
      isLoading: isLoading ?? this.isLoading,
      isStreaming: isStreaming ?? this.isStreaming,
      queuedInputCount: queuedInputCount ?? this.queuedInputCount,
      streamingContent: streamingContent ?? this.streamingContent,
      quickActions: quickActions ?? this.quickActions,
      error: error,
      progressStage: progressStage,
      progressMessage: progressMessage,
      progressHistory: progressHistory ?? this.progressHistory,
      generationSteps: generationSteps ?? this.generationSteps,
      activeJobId: clearActiveJobId ? null : (activeJobId ?? this.activeJobId),
      currentGenerationId: clearCurrentGenerationId
          ? null
          : (currentGenerationId ?? this.currentGenerationId),
      hasPartialMessage: hasPartialMessage ?? this.hasPartialMessage,
      interruptionType: clearInterruptionType
          ? null
          : (interruptionType ?? this.interruptionType),
      awaitingBridging: awaitingBridging ?? this.awaitingBridging,
      signalHint: clearSignalHint ? null : (signalHint ?? this.signalHint),
      signalHintType: clearSignalHintType
          ? null
          : (signalHintType ?? this.signalHintType),
      isVoiceStreaming: isVoiceStreaming ?? this.isVoiceStreaming,
      partialTranscription: clearPartialTranscription
          ? null
          : (partialTranscription ?? this.partialTranscription),
      voiceAmplitude: voiceAmplitude ?? this.voiceAmplitude,
      memoryExtractedToast: clearMemoryExtractedToast
          ? null
          : (memoryExtractedToast ?? this.memoryExtractedToast),
      historyHasMore: historyHasMore ?? this.historyHasMore,
      isLoadingHistory: isLoadingHistory ?? this.isLoadingHistory,
      oldestMessageId: clearOldestMessageId
          ? null
          : (oldestMessageId ?? this.oldestMessageId),
    );
  }

  @override
  List<Object?> get props => [
        messages,
        sessionId,
        isLoading,
        isStreaming,
        queuedInputCount,
        streamingContent,
        quickActions,
        error,
        progressStage,
        progressMessage,
        progressHistory,
        generationSteps,
        activeJobId,
        currentGenerationId,
        hasPartialMessage,
        interruptionType,
        awaitingBridging,
        signalHint,
        signalHintType,
        isVoiceStreaming,
        partialTranscription,
        voiceAmplitude,
        memoryExtractedToast,
        historyHasMore,
        isLoadingHistory,
        oldestMessageId,
      ];
}
