import 'dart:async';
import 'dart:io';
import 'package:flutter/foundation.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../domain/entities/chat_message.dart';
import '../../domain/entities/generation_step.dart';
import '../../domain/entities/tool_execution_step.dart';
import '../../domain/repositories/assistant_repository.dart';
import '../../data/datasources/assistant_remote_datasource.dart';
import '../../data/datasources/pending_action_datasource.dart';
import '../../../../core/location/location_service.dart';
import '../../../../core/network/websocket_service.dart';

export 'assistant_events.dart';
export 'assistant_state.dart';
import 'assistant_events.dart';
import 'assistant_state.dart';

part 'assistant_stream_handlers.dart';
part 'assistant_action_handlers.dart';

/// AssistantBloc -- orchestrates chat messaging, streaming, voice input,
/// WebSocket slow-path handling, and message actions.
///
/// Heavy handler logic is split into mixins via `part` files:
/// - [AssistantStreamHandlers]: stream/WebSocket event processing
/// - [AssistantActionHandlers]: regenerate, edit, suggestion, task, travel
class AssistantBloc extends Bloc<AssistantEvent, AssistantState>
    with AssistantStreamHandlers, AssistantActionHandlers {
  /// Chat runs in WebSocket mode only.
  static const bool useWebSocketChat = true;

  /// Signal types that interrupt the active generation stream.
  static const _interruptingSignals = {'correction', 'cancel'};

  /// Human-readable labels for intervention signal hints shown to the user.
  static const _signalHintLabels = <String, String>{
    'correction': '纠正信号已发送',
    'cancel': '取消信号已发送',
    'additive': '补充信息已接收，回复继续中',
    'confirm': '确认信号已发送，回复继续中',
    'digression': '话题切换已排队，当前回复完成后处理',
  };

  @override
  final AssistantRepository repository;
  @override
  final PendingActionDatasource? pendingActionDatasource;
  final LocationService? locationService;
  @override
  final WebSocketService? webSocketService;
  StreamSubscription<StreamEvent>? _streamSubscription;
  StreamSubscription<StreamEvent>? _wsSubscription;
  @override
  Timer? wsIdleTimer;
  final List<String> _queuedMessages = <String>[];
  bool _queuedDispatchScheduled = false;

  /// Track processed bridging event IDs to prevent dedup false-positives.
  final Set<String> _processedBridgingIds = {};
  static const _maxBridgingIds = 20;

  @override
  Set<String> get processedBridgingIds => _processedBridgingIds;
  @override
  int get maxBridgingIds => _maxBridgingIds;

  /// Cancellable timer for signal hint auto-dismiss.
  Timer? _signalHintTimer;

  @override
  Timer? get signalHintTimer => _signalHintTimer;
  @override
  set signalHintTimer(Timer? value) => _signalHintTimer = value;

  /// Cancellable timer for bridging timeout safety (5s).
  Timer? _bridgingTimeoutTimer;

  /// Safety timeout: auto-clear streaming state if backend never responds
  /// to a voice transcription (V-M-2).
  Timer? _voiceResponseTimeoutTimer;

  @override
  Timer? get bridgingTimeoutTimer => _bridgingTimeoutTimer;
  @override
  set bridgingTimeoutTimer(Timer? value) => _bridgingTimeoutTimer = value;

  AssistantBloc({
    required this.repository,
    this.pendingActionDatasource,
    this.locationService,
    this.webSocketService,
  }) : super(const AssistantInitial()) {
    // Core messaging
    on<AssistantSendMessage>(_onSendMessage);
    on<AssistantStreamMessage>(_onStreamMessage);
    on<AssistantDispatchQueuedMessage>(_onDispatchQueuedMessage);
    on<AssistantVoiceMessage>(_onVoiceMessage);
    on<VoiceTranscriptionReceived>(_onVoiceTranscriptionReceived);

    // Stream events (from AssistantStreamHandlers mixin)
    on<AssistantStreamChunkReceived>(_onStreamChunkReceived);
    on<AssistantStreamCompleted>(_onStreamCompleted);
    on<AssistantStreamSessionReceived>(_onStreamSessionReceived);
    on<AssistantStreamProgressReceived>(_onStreamProgressReceived);
    on<AssistantStreamThinkingReceived>(_onStreamThinkingReceived);
    on<AssistantStreamThinkingStarted>(_onStreamThinkingStarted);
    on<AssistantStreamErrorReceived>(_onStreamErrorReceived);
    on<AssistantStreamToolExecutionReceived>(_onStreamToolExecutionReceived);
    on<AssistantStreamToolProgressReceived>(_onStreamToolProgressReceived);
    on<AssistantStreamConfirmCardReceived>(_onStreamConfirmCardReceived);
    on<AssistantStreamAskUserQuestionReceived>(
        _onStreamAskUserQuestionReceived);
    on<AssistantRouteInfoReceived>(_onRouteInfoReceived);
    on<AssistantSlowPathResultReceived>(_onSlowPathResultReceived);
    on<AssistantTaskQueued>(_onTaskQueued);
    on<AssistantBackgroundJobStarted>(_onBackgroundJobStarted);

    // Session restoration & history
    on<AssistantRestoreSession>(_onRestoreSession);
    on<AssistantLoadHistory>(_onLoadHistory);
    on<LoadMoreHistoryRequested>(_onLoadMoreHistory);
    on<AssistantClearChat>(_onClearChat);
    on<AssistantLoadQuickActions>(_onLoadQuickActions);
    on<AssistantQuickActionTapped>(_onQuickActionTapped);

    // Message actions (from AssistantActionHandlers mixin)
    on<AssistantRegenerateMessage>(_onRegenerateMessage);
    on<AssistantEditMessage>(_onEditMessage);
    on<AssistantDismissSuggestion>(_onDismissSuggestion);
    on<AssistantActOnSuggestion>(_onActOnSuggestion);
    on<AssistantAssignTask>(_onAssignTask);
    on<AssistantConfirmTravelPlan>(_onConfirmTravelPlan);
    on<AssistantSyncPendingActions>(_onSyncPendingActions);

    // Stop generation
    on<AssistantStopGeneration>(_onStopGeneration);

    // Feedback
    on<AssistantFeedbackSubmitted>(_onFeedbackSubmitted);

    // Full-duplex events
    on<AssistantPartialContentReceived>(_onPartialContentReceived);
    on<AssistantBridgingReceived>(_onBridgingReceived);
    on<AssistantGenerationStateReceived>(_onGenerationStateReceived);
    on<AssistantSidekickInsightReceived>(_onSidekickInsightReceived);
    on<AssistantSignalHintReceived>(_onSignalHintReceived);
    on<AssistantSignalHintDismissed>(_onSignalHintDismissed);

    // Voice streaming events (PLAN-009)
    on<VoiceStreamStartRequested>(_onVoiceStreamStart);
    on<VoiceStreamChunkReady>(_onVoiceStreamChunk);
    on<VoiceStreamEndRequested>(_onVoiceStreamEnd);
    on<VoiceStreamCancelRequested>(_onVoiceStreamCancel);
    on<VoiceStreamTranscriptionReceived>(_onVoiceStreamTranscription);

    // System intelligence events (PLAN-012)
    on<MemoryExtractedReceived>(_onMemoryExtracted);
  }

  @override
  void onChange(Change<AssistantState> change) {
    super.onChange(change);
    final previous = change.currentState;
    final next = change.nextState;
    if (previous is AssistantLoaded &&
        next is AssistantLoaded &&
        previous.isStreaming &&
        !next.isStreaming &&
        !next.awaitingBridging) {
      _scheduleQueuedDispatch();
    }
  }

  /// Start listening to WebSocket events for slow/hybrid path results
  void startWebSocketListening() {
    _wsSubscription?.cancel();
    _wsSubscription = repository.listenWebSocketEvents().listen(
      (event) {
        add(AssistantSlowPathResultReceived(event));
      },
      onError: (error) {
        // WebSocket errors are non-fatal; reconnection handled by WebSocketService
      },
    );
  }

  /// Stop listening to WebSocket events
  void stopWebSocketListening() {
    _wsSubscription?.cancel();
    _wsSubscription = null;
  }

  @override
  Future<void> close() {
    _streamSubscription?.cancel();
    _wsSubscription?.cancel();
    wsIdleTimer?.cancel();
    _signalHintTimer?.cancel();
    _bridgingTimeoutTimer?.cancel();
    _voiceResponseTimeoutTimer?.cancel();
    _memoryToastTimer?.cancel();
    _queuedMessages.clear();
    _queuedDispatchScheduled = false;
    return super.close();
  }

  // ── Core message handlers ──────────────────────────────────────────

  Future<void> _onSendMessage(
    AssistantSendMessage event,
    Emitter<AssistantState> emit,
  ) async {
    final currentState = state is AssistantLoaded
        ? state as AssistantLoaded
        : const AssistantLoaded();

    final userMessage = ChatMessage(
      id: DateTime.now().millisecondsSinceEpoch.toString(),
      sessionId: currentState.sessionId ?? '',
      role: MessageRole.user,
      content: event.message,
      createdAt: DateTime.now(),
    );

    emit(currentState.copyWith(
      messages: [...currentState.messages, userMessage],
      isLoading: true,
      error: null,
    ));

    final result = await repository.sendMessage(
      message: event.message,
      sessionId: currentState.sessionId,
    );

    result.fold(
      (failure) {
        emit(currentState.copyWith(
          messages: [...currentState.messages, userMessage],
          isLoading: false,
          error: failure.message,
        ));
      },
      (response) {
        emit(currentState.copyWith(
          messages: [...currentState.messages, userMessage, response],
          sessionId: response.sessionId,
          isLoading: false,
        ));
      },
    );
  }

  Future<void> _onStreamMessage(
    AssistantStreamMessage event,
    Emitter<AssistantState> emit,
  ) async {
    final currentState = state is AssistantLoaded
        ? state as AssistantLoaded
        : const AssistantLoaded();

    // Full-duplex fast path: when streaming is active, send as intervention
    // signal via a lightweight path that preserves the current stream.
    // Only CORRECTION / CANCEL will interrupt; ADDITIVE / CONFIRM / DIGRESSION
    // let the generation continue seamlessly.
    if (currentState.isStreaming) {
      await _sendInterventionSignal(
        message: event.message,
        emit: emit,
      );
      return;
    }

    if (_queuedDispatchScheduled || _queuedMessages.isNotEmpty) {
      _queuedMessages.add(event.message);
      final queuedUserMessage = ChatMessage(
        id: DateTime.now().millisecondsSinceEpoch.toString(),
        sessionId: currentState.sessionId ?? '',
        role: MessageRole.user,
        content: event.message,
        createdAt: DateTime.now(),
      );
      emit(currentState.copyWith(
        messages: [...currentState.messages, queuedUserMessage],
        queuedInputCount: _queuedMessages.length,
        error: null,
        progressStage: 'queued',
        progressMessage: '当前回复进行中，已排队${_queuedMessages.length}条消息',
      ));
      _scheduleQueuedDispatch();
      return;
    }

    await _startStreamMessage(
      message: event.message,
      emit: emit,
      appendUserMessage: true,
    );
  }

  Future<void> _onDispatchQueuedMessage(
    AssistantDispatchQueuedMessage event,
    Emitter<AssistantState> emit,
  ) async {
    _queuedDispatchScheduled = false;

    if (state is! AssistantLoaded) {
      _queuedMessages.insert(0, event.message);
      return;
    }
    final currentState = state as AssistantLoaded;
    if (currentState.isStreaming || currentState.awaitingBridging) {
      _queuedMessages.insert(0, event.message);
      return;
    }

    await _startStreamMessage(
      message: event.message,
      emit: emit,
      appendUserMessage: false,
    );
  }

  Future<void> _startStreamMessage({
    required String message,
    required Emitter<AssistantState> emit,
    required bool appendUserMessage,
  }) async {
    final currentState = state is AssistantLoaded
        ? state as AssistantLoaded
        : const AssistantLoaded();

    final updatedMessages = <ChatMessage>[
      ...currentState.messages,
      if (appendUserMessage)
        ChatMessage(
          id: DateTime.now().millisecondsSinceEpoch.toString(),
          sessionId: currentState.sessionId ?? '',
          role: MessageRole.user,
          content: message,
          createdAt: DateTime.now(),
        ),
      ChatMessage(
        id: DateTime.now().millisecondsSinceEpoch.toString(),
        sessionId: currentState.sessionId ?? '',
        role: MessageRole.assistant,
        content: '',
        generationSteps: const [],
        isStreaming: true,
        createdAt: DateTime.now(),
      ),
    ];

    emit(currentState.copyWith(
      messages: updatedMessages,
      isStreaming: true,
      queuedInputCount: _queuedMessages.length,
      streamingContent: '',
      generationSteps: [],
      error: null,
      progressStage: null,
      progressMessage: null,
      progressHistory: [],
    ));

    final loc = await _resolveLocation();
    final result = await repository.sendChatMessage(
      message: message,
      sessionId: currentState.sessionId,
      latitude: loc.latitude,
      longitude: loc.longitude,
      locationName: loc.locationName,
    );

    result.fold(
      (failure) {
        add(AssistantStreamErrorReceived(failure.message));
      },
      (response) {
        // Full-duplex: signal_accepted response (intervention signal, not a new job).
        // This is a safety fallback — the primary intervention path is
        // _sendInterventionSignal which preserves the active stream.
        if (response.isSignalAccepted) {
          final hint = _signalHintLabels[response.signalType] ?? '信号已发送';
          final latestState = state;
          if (latestState is AssistantLoaded) {
            final cleanedMessages = latestState.messages
                .where((m) => !(m.role == MessageRole.assistant &&
                    m.isStreaming && m.content.isEmpty))
                .toList();
            emit(latestState.copyWith(
              messages: cleanedMessages,
              isStreaming: false,
              isLoading: false,
            ));
          }
          add(AssistantSignalHintReceived(hint));
          return;
        }

        // Set session and active job for WS correlation
        debugPrint(
          '[CHAT DISPATCH] accepted session=${response.sessionId} job=${response.jobId} '
          'route=${response.routeType}',
        );
        add(AssistantStreamSessionReceived(response.sessionId));
        webSocketService?.setActiveJob(response.jobId);
        final latestState = state;
        if (latestState is AssistantLoaded) {
          emit(latestState.copyWith(activeJobId: response.jobId));
        }
        if (response.routeType == 'slow') {
          add(AssistantTaskQueued(response.jobId));
        } else if (response.routeType == 'hybrid') {
          add(const AssistantRouteInfoReceived('hybrid'));
        } else {
          add(const AssistantRouteInfoReceived('fast'));
        }
        // Results will arrive via existing _wsSubscription
      },
    );
  }

  // ── Intervention signal (lightweight, stream-preserving) ──────────

  /// Sends a user message as an intervention signal without disrupting the
  /// current streaming generation.  Only CORRECTION / CANCEL will actually
  /// interrupt the stream; ADDITIVE / CONFIRM / DIGRESSION let it continue.
  Future<void> _sendInterventionSignal({
    required String message,
    required Emitter<AssistantState> emit,
  }) async {
    final currentState = state is AssistantLoaded
        ? state as AssistantLoaded
        : const AssistantLoaded();

    // Show the user's message bubble immediately — no ghost placeholder,
    // no streamingContent reset, so the active generation stays intact.
    final userMessage = ChatMessage(
      id: DateTime.now().millisecondsSinceEpoch.toString(),
      sessionId: currentState.sessionId ?? '',
      role: MessageRole.user,
      content: message,
      createdAt: DateTime.now(),
    );
    emit(currentState.copyWith(
      messages: [...currentState.messages, userMessage],
    ));

    final loc = await _resolveLocation();
    final result = await repository.sendChatMessage(
      message: message,
      sessionId: currentState.sessionId,
      latitude: loc.latitude,
      longitude: loc.longitude,
      locationName: loc.locationName,
    );

    result.fold(
      (failure) {
        add(AssistantStreamErrorReceived(failure.message));
      },
      (response) {
        if (!response.isSignalAccepted) {
          // Edge case: backend didn't classify as intervention (e.g. session
          // became idle between our check and the API call).  Fall through to
          // normal dispatch handling.
          debugPrint(
            '[CHAT INTERVENTION] non-signal response, falling back to normal dispatch',
          );
          add(AssistantStreamSessionReceived(response.sessionId));
          webSocketService?.setActiveJob(response.jobId);
          final latestState = state;
          if (latestState is AssistantLoaded) {
            emit(latestState.copyWith(activeJobId: response.jobId));
          }
          return;
        }

        final signalType = response.signalType;
        final isInterrupting = _interruptingSignals.contains(signalType);
        final hint = _signalHintLabels[signalType] ?? '信号已发送';

        if (isInterrupting) {
          // CORRECTION / CANCEL: mark as awaiting bridging to prevent
          // queued message dispatch race condition.
          // Keep isStreaming=true until bridging/generationState arrives.
          final latestState = state;
          if (latestState is AssistantLoaded) {
            emit(latestState.copyWith(
              awaitingBridging: true,
              interruptionType: signalType,
            ));
          }
          // Safety timeout: if no bridging event arrives within 5s,
          // auto-clear awaitingBridging and stop streaming.
          _bridgingTimeoutTimer?.cancel();
          _bridgingTimeoutTimer = Timer(
            const Duration(seconds: 5),
            () {
              if (isClosed) return;
              final s = state;
              if (s is AssistantLoaded && s.awaitingBridging) {
                add(const AssistantGenerationStateReceived(
                  action: 'cancel',
                ));
              }
            },
          );
        } else if (signalType == 'additive') {
          // ADDITIVE: inject inline acknowledgment message (E-005)
          final latestState = state;
          if (latestState is AssistantLoaded) {
            final ackMessage = ChatMessage(
              id: 'ack-${DateTime.now().microsecondsSinceEpoch}',
              sessionId: latestState.sessionId ?? '',
              role: MessageRole.assistant,
              content: '已传达给助手',
              intent: 'additive_ack',
              createdAt: DateTime.now(),
            );
            emit(latestState.copyWith(
              messages: [...latestState.messages, ackMessage],
            ));
          }
        }
        // ADDITIVE / CONFIRM / DIGRESSION: stream continues uninterrupted.

        add(AssistantSignalHintReceived(hint, signalType: signalType));
      },
    );
  }

  // ── Voice input handlers ──────────────────────────────────────────

  Future<void> _onVoiceMessage(
    AssistantVoiceMessage event,
    Emitter<AssistantState> emit,
  ) async {
    final currentState = state is AssistantLoaded
        ? state as AssistantLoaded
        : const AssistantLoaded();

    final streamingAssistantMessage = ChatMessage(
      id: DateTime.now().millisecondsSinceEpoch.toString(),
      sessionId: currentState.sessionId ?? '',
      role: MessageRole.assistant,
      content: '',
      generationSteps: const [],
      isStreaming: true,
      createdAt: DateTime.now(),
    );

    emit(currentState.copyWith(
      messages: [...currentState.messages, streamingAssistantMessage],
      isStreaming: true,
      isLoading: true,
      streamingContent: '',
      generationSteps: [],
      error: null,
      progressStage: null,
      progressMessage: null,
      progressHistory: [],
    ));

    final loc = await _resolveLocation();

    try {
      await for (final streamEvent in repository.streamVoiceMessage(
        audioPath: event.audioPath,
        sessionId: currentState.sessionId,
        latitude: loc.latitude,
        longitude: loc.longitude,
        locationName: loc.locationName,
      )) {
        switch (streamEvent.type) {
          case StreamEventType.transcription:
            final text = streamEvent.content?.trim() ?? '';
            if (text.isNotEmpty) {
              add(VoiceTranscriptionReceived(text));
            }
            break;
          case StreamEventType.session:
            if (streamEvent.sessionId != null) {
              add(AssistantStreamSessionReceived(streamEvent.sessionId!));
            }
            break;
          case StreamEventType.route:
            if (streamEvent.routeType != null) {
              add(AssistantRouteInfoReceived(streamEvent.routeType!));
            }
            break;
          case StreamEventType.queued:
            if (streamEvent.jobId != null) {
              webSocketService?.setActiveJob(streamEvent.jobId!);
              add(AssistantTaskQueued(streamEvent.jobId));
            }
            break;
          case StreamEventType.backgroundJob:
            if (streamEvent.jobId != null) {
              webSocketService?.setActiveJob(streamEvent.jobId!);
              add(AssistantBackgroundJobStarted(streamEvent.jobId));
            }
            break;
          case StreamEventType.error:
            add(AssistantStreamErrorReceived(
              streamEvent.message ?? '语音消息发送失败，请稍后重试',
            ));
            break;
          default:
            break;
        }
      }
    } finally {
      _deleteAudioFile(event.audioPath);
    }
  }

  void _onVoiceTranscriptionReceived(
    VoiceTranscriptionReceived event,
    Emitter<AssistantState> emit,
  ) {
    if (state is! AssistantLoaded) return;
    final currentState = state as AssistantLoaded;

    final userMessage = ChatMessage(
      id: DateTime.now().millisecondsSinceEpoch.toString(),
      sessionId: currentState.sessionId ?? '',
      role: MessageRole.user,
      content: event.text,
      createdAt: DateTime.now(),
    );

    final messages = List<ChatMessage>.from(currentState.messages);

    // Finalize any existing streaming assistant message before inserting new ones
    final streamingIdx = messages.lastIndexWhere((m) => m.isStreaming);
    if (streamingIdx >= 0) {
      messages[streamingIdx] =
          messages[streamingIdx].copyWith(isStreaming: false);
    }

    // Add user message
    messages.add(userMessage);

    // Add streaming assistant placeholder so incoming AI content events
    // have a target message to update (same pattern as _onSendMessage).
    messages.add(ChatMessage(
      id: 'streaming-${DateTime.now().millisecondsSinceEpoch}',
      sessionId: currentState.sessionId ?? '',
      role: MessageRole.assistant,
      content: '',
      createdAt: DateTime.now(),
      isStreaming: true,
    ));

    emit(currentState.copyWith(
      messages: messages,
      isLoading: true,
      isStreaming: true,
      streamingContent: '',
      generationSteps: [],
      progressStage: null,
      progressMessage: null,
    ));

    // V-M-2: Safety timeout — if backend never dispatches a voice_chat_started
    // or content event within 15s, auto-clear the stuck streaming state.
    _voiceResponseTimeoutTimer?.cancel();
    _voiceResponseTimeoutTimer = Timer(const Duration(seconds: 15), () {
      if (isClosed) return;
      final s = state;
      if (s is AssistantLoaded && s.isStreaming && s.streamingContent.isEmpty) {
        add(AssistantStreamErrorReceived('语音处理超时，请重试'));
      }
    });
  }

  // ── Session restoration & history ─────────────────────────────────

  Future<void> _onRestoreSession(
    AssistantRestoreSession event,
    Emitter<AssistantState> emit,
  ) async {
    // Skip if session already set (e.g. from a previous restore or message send)
    if (state is AssistantLoaded && (state as AssistantLoaded).sessionId != null) {
      return;
    }

    // Load cross-session history (no session filter) to show recent messages
    // regardless of which session they belong to.
    final result = await repository.loadMoreHistory(limit: 50);

    result.fold(
      (_) {}, // Silently ignore errors on cold start
      (data) {
        if (data.messages.isEmpty) return;

        // Extract session_id from the most recent message for future use
        final latestSessionId = data.messages.last.sessionId;

        emit(AssistantLoaded(
          messages: data.messages,
          sessionId: latestSessionId,
          historyHasMore: data.hasMore,
          oldestMessageId: data.oldestId,
        ));
      },
    );
  }

  Future<void> _onLoadHistory(
    AssistantLoadHistory event,
    Emitter<AssistantState> emit,
  ) async {
    emit(const AssistantLoaded(isLoading: true));

    final result = await repository.loadMoreHistory(
      sessionId: event.sessionId,
      limit: 50,
    );

    result.fold(
      (failure) => emit(AssistantLoaded(error: failure.message)),
      (data) => emit(AssistantLoaded(
        messages: data.messages,
        sessionId: event.sessionId,
        historyHasMore: data.hasMore,
        oldestMessageId: data.oldestId,
      )),
    );
  }

  Future<void> _onLoadMoreHistory(
    LoadMoreHistoryRequested event,
    Emitter<AssistantState> emit,
  ) async {
    if (state is! AssistantLoaded) return;
    final current = state as AssistantLoaded;
    if (current.isLoadingHistory) return;
    if (!current.historyHasMore) return;

    emit(current.copyWith(isLoadingHistory: true));

    try {
      final result = await repository.loadMoreHistory(
        beforeId: current.oldestMessageId,
      );
      result.fold(
        (failure) {
          emit(current.copyWith(
            isLoadingHistory: false,
            error: failure.message,
          ));
        },
        (data) {
          final merged = [...data.messages, ...current.messages];
          final capped =
              merged.length > 200 ? merged.sublist(0, 200) : merged;
          emit(current.copyWith(
            messages: capped,
            isLoadingHistory: false,
            historyHasMore: data.hasMore,
            oldestMessageId: data.oldestId ?? current.oldestMessageId,
          ));
        },
      );
    } catch (_) {
      emit(current.copyWith(isLoadingHistory: false));
    }
  }

  void _onClearChat(
    AssistantClearChat event,
    Emitter<AssistantState> emit,
  ) {
    _queuedMessages.clear();
    _queuedDispatchScheduled = false;
    emit(const AssistantLoaded());
  }

  Future<void> _onLoadQuickActions(
    AssistantLoadQuickActions event,
    Emitter<AssistantState> emit,
  ) async {
    final currentState = state is AssistantLoaded
        ? state as AssistantLoaded
        : const AssistantLoaded();

    final result = await repository.getQuickActions();

    result.fold(
      (failure) => null,
      (actions) => emit(currentState.copyWith(quickActions: actions)),
    );
  }

  void _onQuickActionTapped(
    AssistantQuickActionTapped event,
    Emitter<AssistantState> emit,
  ) {
    add(AssistantStreamMessage(event.action.action));
  }

  // ── Private helpers ───────────────────────────────────────────────

  Future<({double? latitude, double? longitude, String? locationName})>
      _resolveLocation() async {
    if (locationService == null) {
      return (latitude: null, longitude: null, locationName: null);
    }
    try {
      final loc = await locationService!.getCurrentLocation();
      if (loc != null) {
        return (
          latitude: loc.latitude,
          longitude: loc.longitude,
          locationName: loc.cityName
        );
      }
    } catch (_) {}
    return (latitude: null, longitude: null, locationName: null);
  }

  void _deleteAudioFile(String path) {
    try {
      final file = File(path);
      if (file.existsSync()) file.deleteSync();
    } catch (_) {}
  }

  void _scheduleQueuedDispatch() {
    if (isClosed || _queuedDispatchScheduled || _queuedMessages.isEmpty) return;
    final nextMessage = _queuedMessages.removeAt(0);
    _queuedDispatchScheduled = true;
    add(AssistantDispatchQueuedMessage(nextMessage));
  }

  /// Handle stop generation: stop local streaming state and keep received content.
  Future<void> _onStopGeneration(
    AssistantStopGeneration event,
    Emitter<AssistantState> emit,
  ) async {
    _streamSubscription?.cancel();
    _streamSubscription = null;
    wsIdleTimer?.cancel();
    wsIdleTimer = null;

    if (state is! AssistantLoaded) return;
    final currentState = state as AssistantLoaded;
    final sessionId = currentState.sessionId;
    if (!currentState.isStreaming) {
      if (sessionId != null && sessionId.isNotEmpty) {
        await repository.cancelGeneration(sessionId: sessionId);
      }
      return;
    }

    final stoppedMessage = ChatMessage(
      id: DateTime.now().millisecondsSinceEpoch.toString(),
      sessionId: currentState.sessionId ?? '',
      role: MessageRole.assistant,
      content: currentState.streamingContent,
      generationSteps: currentState.generationSteps,
      isStopped: true,
      createdAt: DateTime.now(),
    );

    final updatedMessages = _replaceOrAppendStreamingAssistantMessage(
      currentState.messages,
      stoppedMessage,
    );

    emit(currentState.copyWith(
      messages: updatedMessages,
      isStreaming: false,
      awaitingBridging: false,
      queuedInputCount: _queuedMessages.length,
      streamingContent: '',
      generationSteps: [],
      progressHistory: [],
      progressStage: null,
      progressMessage: null,
      clearActiveJobId: true,
    ));
    _bridgingTimeoutTimer?.cancel();
    _bridgingTimeoutTimer = null;

    webSocketService?.clearActiveJob();
    if (sessionId != null && sessionId.isNotEmpty) {
      await repository.cancelGeneration(sessionId: sessionId);
    }
  }

  // _dispatchStreamEvent is defined in AssistantStreamHandlers mixin

  // ---- Voice Streaming Handlers (PLAN-009) ----

  void _onVoiceStreamStart(
    VoiceStreamStartRequested event,
    Emitter<AssistantState> emit,
  ) {
    if (state is! AssistantLoaded) return;
    final s = state as AssistantLoaded;
    emit(s.copyWith(
      isVoiceStreaming: true,
      clearPartialTranscription: true,
      voiceAmplitude: 0.0,
    ));
  }

  void _onVoiceStreamChunk(
    VoiceStreamChunkReady event,
    Emitter<AssistantState> emit,
  ) {
    if (state is! AssistantLoaded) return;
    final s = state as AssistantLoaded;

    // V-M-3: Check WS connection — if disconnected, clear state once and return.
    // Don't dispatch VoiceStreamCancelRequested to avoid double state transitions.
    if (webSocketService == null || !webSocketService!.isConnected) {
      if (!s.isVoiceStreaming) return; // Already handled
      emit(s.copyWith(
        isVoiceStreaming: false,
        clearPartialTranscription: true,
      ));
      return;
    }
    // H-3: safe call; M-3: event.audioBytes is already Uint8List
    webSocketService?.sendAudioChunk(event.audioBytes);
  }

  void _onVoiceStreamEnd(
    VoiceStreamEndRequested event,
    Emitter<AssistantState> emit,
  ) {
    if (state is! AssistantLoaded) return;
    final s = state as AssistantLoaded;

    // V-M-5: Check WS connection — if dropped, user's voice is lost.
    if (webSocketService == null || !webSocketService!.isConnected) {
      emit(s.copyWith(
        isVoiceStreaming: false,
        clearPartialTranscription: true,
      ));
      add(AssistantStreamErrorReceived('网络已断开，语音消息未发送'));
      return;
    }

    webSocketService?.sendAudioEnd();
    emit(s.copyWith(isVoiceStreaming: false));
  }

  void _onVoiceStreamCancel(
    VoiceStreamCancelRequested event,
    Emitter<AssistantState> emit,
  ) {
    // V-M-6: Only send cancel to backend if WS is connected.
    if (webSocketService != null && webSocketService!.isConnected) {
      webSocketService!.sendAudioCancel();
    }
    if (state is! AssistantLoaded) return;
    final s = state as AssistantLoaded;
    emit(s.copyWith(
      isVoiceStreaming: false,
      clearPartialTranscription: true,
    ));
  }

  void _onVoiceStreamTranscription(
    VoiceStreamTranscriptionReceived event,
    Emitter<AssistantState> emit,
  ) {
    if (state is! AssistantLoaded) return;
    final s = state as AssistantLoaded;
    if (event.isCancelled) {
      emit(s.copyWith(
        isVoiceStreaming: false,
        clearPartialTranscription: true,
      ));
      return;
    }
    if (event.isPartial) {
      emit(s.copyWith(partialTranscription: event.text));
    } else {
      // Final transcription — insert user message bubble
      add(VoiceTranscriptionReceived(event.text));
      emit(s.copyWith(
        isVoiceStreaming: false,
        clearPartialTranscription: true,
      ));
    }
  }

  // ---- Memory Extracted Handler (PLAN-012) ----

  Timer? _memoryToastTimer;

  void _onMemoryExtracted(
    MemoryExtractedReceived event,
    Emitter<AssistantState> emit,
  ) {
    if (state is! AssistantLoaded) return;
    final s = state as AssistantLoaded;
    _memoryToastTimer?.cancel();
    emit(s.copyWith(memoryExtractedToast: event.summary));
    // Auto-dismiss after 3s
    _memoryToastTimer = Timer(const Duration(seconds: 3), () {
      if (!isClosed && state is AssistantLoaded) {
        // ignore: invalid_use_of_visible_for_testing_member
        emit((state as AssistantLoaded).copyWith(
          clearMemoryExtractedToast: true,
        ));
      }
    });
  }
}
