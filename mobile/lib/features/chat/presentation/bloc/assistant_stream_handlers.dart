part of 'assistant_bloc.dart';

/// Stream event handlers extracted from AssistantBloc.
///
/// Handles: chunk, completed, session, progress, thinking, error,
/// tool execution, confirm card, route info, task queued,
/// background job, slow path result.
mixin AssistantStreamHandlers on Bloc<AssistantEvent, AssistantState> {
  // These are provided by AssistantBloc
  AssistantRepository get repository;
  Timer? get wsIdleTimer;
  set wsIdleTimer(Timer? value);
  WebSocketService? get webSocketService;

  // Bridging dedup tracking
  Set<String> get processedBridgingIds;
  int get maxBridgingIds;

  // Signal hint timer
  Timer? get signalHintTimer;
  set signalHintTimer(Timer? value);

  // Bridging timeout timer (set by _sendInterventionSignal)
  Timer? get bridgingTimeoutTimer;
  set bridgingTimeoutTimer(Timer? value);

  /// Throttle: track last time we emitted messages list update for chunks.
  DateTime _lastChunkEmitTime = DateTime(2000);
  static const int _chunkThrottleMs = 100;

  /// Cached regex for stripping leaked XML function tags from LLM output.
  static final RegExp _functionTagRegex =
      RegExp(r'<function.*?>.*?</function>', dotAll: true);

  /// Internal error markers that should never be shown to the user.
  static final List<String> _internalErrorMarkers = [
    'stream ended unexpectedly',
    'cli_alive=',
    'cli_rc=',
    'query_closed=',
    'pending_len=',
    'receive iterator',
    'Actor failed',
    'StopAsyncIteration',
    'RuntimeError',
    'Traceback',
    'session_id=',
  ];

  /// Sanitize raw error strings into user-friendly messages.
  ///
  /// Backend should already sanitize, but this acts as defense-in-depth
  /// so raw internal diagnostics never appear as chat bubbles.
  static String _sanitizeErrorForDisplay(String raw) {
    final lower = raw.toLowerCase();
    if (lower.contains('timeout') || lower.contains('dioexception')) {
      return '请求超时，请稍后重试';
    }
    for (final marker in _internalErrorMarkers) {
      if (raw.contains(marker)) {
        return '处理出错了，请重新发送';
      }
    }
    // Heuristic: long errors or those with session UUIDs are internal
    if (raw.length > 120) {
      return '后台处理失败，请重试';
    }
    return raw;
  }

  void _onStreamChunkReceived(
    AssistantStreamChunkReceived event,
    Emitter<AssistantState> emit,
  ) {
    if (state is! AssistantLoaded) return;
    final currentState = state as AssistantLoaded;

    // V-M-2: First content chunk means backend responded — cancel timeout.
    final bloc = this as AssistantBloc;
    if (bloc._voiceResponseTimeoutTimer != null) {
      bloc._voiceResponseTimeoutTimer?.cancel();
      bloc._voiceResponseTimeoutTimer = null;
    }

    // Accumulate raw content — defer regex stripping to full-emit path
    final rawContent = currentState.streamingContent + event.chunk;

    final updatedSteps =
        List<GenerationStep>.from(currentState.generationSteps);
    if (updatedSteps.isNotEmpty && updatedSteps.last is ContentStep) {
      final lastStep = updatedSteps.last as ContentStep;
      updatedSteps[updatedSteps.length - 1] = ContentStep(content: lastStep.content + event.chunk);
    } else {
      updatedSteps.add(ContentStep(content: event.chunk));
    }

    final now = DateTime.now();
    final elapsed = now.difference(_lastChunkEmitTime).inMilliseconds;

    if (elapsed < _chunkThrottleMs) {
      // Within throttle window: lightweight update with raw content only.
      // Skip regex stripping and messages list rebuild.
      emit(currentState.copyWith(
        streamingContent: rawContent,
        generationSteps: updatedSteps,
      ));
      return;
    }

    // Outside throttle window: full emit with regex cleaning + messages update.
    _lastChunkEmitTime = now;
    final cleanContent = rawContent.replaceAll(_functionTagRegex, '');

    final updatedMessages = _updateLastStreamingAssistantMessage(
      currentState.messages,
      (message) => message.copyWith(
        content: cleanContent,
        generationSteps: updatedSteps,
      ),
    );

    emit(currentState.copyWith(
      messages: updatedMessages,
      streamingContent: cleanContent,
      generationSteps: updatedSteps,
    ));
  }

  void _onStreamCompleted(
    AssistantStreamCompleted event,
    Emitter<AssistantState> emit,
  ) {
    if (state is! AssistantLoaded) return;
    final currentState = state as AssistantLoaded;
    if (event.clearActiveJobId) {
      _cancelWsTimeout();
    }

    List<MessageProgressStep>? messageProgressHistory;
    if (event.progressHistory != null && event.progressHistory!.isNotEmpty) {
      messageProgressHistory = event.progressHistory!
          .map((p) => MessageProgressStep.fromJson(p))
          .toList();
    } else if (currentState.progressHistory.isNotEmpty) {
      messageProgressHistory = currentState.progressHistory
          .map((p) => MessageProgressStep(
                stage: p.stage,
                message: p.message,
                timestamp: p.timestamp,
                data: p.data,
              ))
          .toList();
    }

    List<ToolExecution>? messageToolExecutions;
    if (event.toolExecutions != null && event.toolExecutions!.isNotEmpty) {
      messageToolExecutions = event.toolExecutions!
          .map((t) => ToolExecution(
                toolName: t['tool_name'] as String? ?? 'unknown',
                status: t['status'] as String? ?? 'success',
                timestamp: t['timestamp'] != null
                    ? DateTime.parse(t['timestamp'] as String)
                    : DateTime.now(),
                result: t['result'] as Map<String, dynamic>?,
                executionId: t['execution_id'] as String?,
                keyResults: t['key_results'] as Map<String, dynamic>?,
                durationMs: t['duration_ms'] as int?,
                summary: t['summary'] as String?,
              ))
          .toList();
    } else if (currentState.generationSteps.any((s) => s is ToolStep)) {
      messageToolExecutions = currentState.generationSteps
          .whereType<ToolStep>()
          .map((s) => s.tool.toEntity())
          .toList();
    }

    // Prefer authoritative final content from done event when available.
    // Streaming content may be incomplete if chunks were lost during
    // WebSocket reconnection or PubSub timing issues.
    final eventContent = event.content ?? '';
    String finalContent;
    if (eventContent.trim().isNotEmpty &&
        eventContent.length >= currentState.streamingContent.length) {
      finalContent = eventContent;
    } else if (currentState.streamingContent.isNotEmpty) {
      finalContent = currentState.streamingContent;
    } else {
      finalContent = eventContent;
    }
    // Strip any leaked function tags (may remain from throttled path)
    finalContent = finalContent.replaceAll(_functionTagRegex, '');

    const noContentPatterns = ['(no content)', '(No content)'];
    if (noContentPatterns.contains(finalContent.trim())) {
      finalContent = '';
    }

    List<GenerationStep> finalGenerationSteps =
        List.from(currentState.generationSteps);

    if (finalContent.isNotEmpty) {
      if (finalGenerationSteps.isNotEmpty &&
          finalGenerationSteps.last is ContentStep) {
        finalGenerationSteps[finalGenerationSteps.length - 1] =
            ContentStep(content: finalContent, isComplete: true);
      } else {
        finalGenerationSteps
            .add(ContentStep(content: finalContent, isComplete: true));
      }
    }

    const backgroundStatusMessage =
        '\u6b63\u5728\u601d\u8003\u662f\u5426\u8fd8\u6709\u5173\u8054\u4e8b\u9879...';
    final isBackgroundCompletion = currentState.progressStage ==
            'background_job' ||
        currentState.generationSteps.any((step) =>
            step is ThinkingStep && step.content == backgroundStatusMessage) ||
        currentState.progressHistory
            .any((step) => step.stage == 'background_job');
    final shouldKeepBackgroundStreaming =
        currentState.activeJobId != null && !event.clearActiveJobId;

    finalGenerationSteps = finalGenerationSteps.map((s) {
      if (s is ThinkingStep && !s.isComplete) {
        return s.copyWith(isComplete: true);
      }
      return s;
    }).toList();

    finalGenerationSteps = finalGenerationSteps.map((s) {
      if (s is ToolStep && s.tool.status == 'start') {
        return s.copyWith(tool: s.tool.copyWith(status: 'success'));
      }
      return s;
    }).toList();

    finalGenerationSteps = finalGenerationSteps.where((step) {
      if (step is ThinkingStep && step.content == backgroundStatusMessage) {
        return false;
      }
      return true;
    }).toList();

    final hasMeaningfulSteps = finalGenerationSteps.any((step) {
      if (step is ToolStep) return true;
      if (step is ContentStep) return step.content.trim().isNotEmpty;
      if (step is ThinkingStep) return step.content.trim().isNotEmpty;
      return false;
    });
    final hasMeaningfulContent = finalContent.trim().isNotEmpty;
    final hasToolExecutions =
        messageToolExecutions != null && messageToolExecutions.isNotEmpty;
    final hasProgress = messageProgressHistory != null &&
        messageProgressHistory.isNotEmpty &&
        messageProgressHistory.any((p) => p.stage != 'background_job');

    if (shouldKeepBackgroundStreaming) {
      final fastMessage = ChatMessage(
        id: event.messageId ?? DateTime.now().millisecondsSinceEpoch.toString(),
        sessionId: currentState.sessionId ?? '',
        role: MessageRole.assistant,
        content: finalContent,
        thinking: _extractThinkingContent(finalGenerationSteps),
        intent: event.intent,
        data: event.data,
        cardType: event.cardType,
        quickActions: event.quickActions,
        progressHistory: messageProgressHistory,
        toolExecutions: messageToolExecutions,
        generationSteps: finalGenerationSteps,
        isStreaming: false,
        createdAt: DateTime.now(),
      );

      final updatedMessages = _replaceOrAppendStreamingAssistantMessage(
        currentState.messages,
        fastMessage,
      );

      emit(currentState.copyWith(
        messages: updatedMessages,
        isStreaming: true,
        streamingContent: '',
        generationSteps: [const ThinkingStep(content: backgroundStatusMessage)],
        progressHistory: [
          ...currentState.progressHistory,
          ProgressStep(
            stage: 'background_job',
            message: backgroundStatusMessage,
            timestamp: DateTime.now(),
          ),
        ],
        progressStage: 'background_job',
        progressMessage: backgroundStatusMessage,
        clearActiveJobId: event.clearActiveJobId,
      ));
      return;
    }

    if (!hasMeaningfulContent &&
        !hasMeaningfulSteps &&
        !hasToolExecutions &&
        !hasProgress) {
      if (isBackgroundCompletion) {
        final noRelatedMessage = ChatMessage(
          id: event.messageId ??
              DateTime.now().millisecondsSinceEpoch.toString(),
          sessionId: currentState.sessionId ?? '',
          role: MessageRole.assistant,
          content:
              '\u6211\u68c0\u67e5\u8fc7\u4e86\uff0c\u6682\u65f6\u6ca1\u6709\u53d1\u73b0\u9700\u8981\u8865\u5145\u7684\u5173\u8054\u4e8b\u9879\u3002',
          createdAt: DateTime.now(),
        );
        final updatedMessages = _replaceOrAppendStreamingAssistantMessage(
          currentState.messages,
          noRelatedMessage,
        );
        emit(currentState.copyWith(
          messages: updatedMessages,
          isStreaming: false,
          awaitingBridging: false,
          streamingContent: '',
          generationSteps: [],
          progressHistory: [],
          progressStage: null,
          progressMessage: null,
          clearActiveJobId: event.clearActiveJobId,
        ));
        bridgingTimeoutTimer?.cancel();
        bridgingTimeoutTimer = null;
        return;
      }

      final cleanedMessages = currentState.messages
          .where((m) => !(m.role == MessageRole.assistant &&
              m.isStreaming &&
              m.content.isEmpty))
          .toList();
      emit(currentState.copyWith(
        messages: cleanedMessages,
        isStreaming: false,
        awaitingBridging: false,
        streamingContent: '',
        generationSteps: [],
        progressHistory: [],
        progressStage: null,
        progressMessage: null,
        clearActiveJobId: event.clearActiveJobId,
      ));
      bridgingTimeoutTimer?.cancel();
      bridgingTimeoutTimer = null;
      return;
    }

    final assistantMessage = ChatMessage(
      id: event.messageId ?? DateTime.now().millisecondsSinceEpoch.toString(),
      sessionId: currentState.sessionId ?? '',
      role: MessageRole.assistant,
      content: finalContent,
      thinking: _extractThinkingContent(finalGenerationSteps),
      intent: event.intent,
      data: event.data,
      cardType: event.cardType,
      quickActions: event.quickActions,
      progressHistory: messageProgressHistory,
      toolExecutions: messageToolExecutions,
      generationSteps: finalGenerationSteps,
      createdAt: DateTime.now(),
    );

    final updatedMessages = _replaceOrAppendStreamingAssistantMessage(
      currentState.messages,
      assistantMessage,
    );

    emit(currentState.copyWith(
      messages: updatedMessages,
      isStreaming: false,
      awaitingBridging: false,
      streamingContent: '',
      generationSteps: [],
      progressHistory: [],
      quickActions: event.quickActions ?? currentState.quickActions,
      progressStage: null,
      progressMessage: null,
      clearActiveJobId: event.clearActiveJobId,
    ));
    bridgingTimeoutTimer?.cancel();
    bridgingTimeoutTimer = null;
  }

  void _onStreamSessionReceived(
    AssistantStreamSessionReceived event,
    Emitter<AssistantState> emit,
  ) {
    if (state is! AssistantLoaded) return;
    final currentState = state as AssistantLoaded;
    emit(currentState.copyWith(sessionId: event.sessionId));
  }

  void _onStreamProgressReceived(
    AssistantStreamProgressReceived event,
    Emitter<AssistantState> emit,
  ) {
    if (state is! AssistantLoaded) return;
    final currentState = state as AssistantLoaded;

    final newStep = ProgressStep(
      stage: event.stage,
      message: event.message,
      timestamp: DateTime.now(),
    );

    emit(currentState.copyWith(
      progressStage: event.stage,
      progressMessage: event.message,
      progressHistory: [...currentState.progressHistory, newStep],
    ));
  }

  void _onStreamThinkingReceived(
    AssistantStreamThinkingReceived event,
    Emitter<AssistantState> emit,
  ) {
    if (state is! AssistantLoaded) return;
    final currentState = state as AssistantLoaded;

    final currentSteps =
        List<GenerationStep>.from(currentState.generationSteps);
    if (currentSteps.isNotEmpty && currentSteps.last is ThinkingStep) {
      final lastThinking = currentSteps.last as ThinkingStep;
      currentSteps[currentSteps.length - 1] = lastThinking.copyWith(
        content: lastThinking.content + event.thinking,
      );
    } else {
      currentSteps.add(ThinkingStep(content: event.thinking));
    }

    final updatedMessages = _updateLastStreamingAssistantMessage(
      currentState.messages,
      (message) => message.copyWith(generationSteps: currentSteps),
    );

    emit(currentState.copyWith(
      messages: updatedMessages,
      generationSteps: currentSteps,
    ));
  }

  void _onStreamThinkingStarted(
    AssistantStreamThinkingStarted event,
    Emitter<AssistantState> emit,
  ) {
    if (state is! AssistantLoaded) return;
    final currentState = state as AssistantLoaded;

    final updatedSteps = [
      ...currentState.generationSteps,
      ThinkingStep(content: event.content)
    ];
    final updatedMessages = _updateLastStreamingAssistantMessage(
      currentState.messages,
      (message) => message.copyWith(generationSteps: updatedSteps),
    );

    emit(currentState.copyWith(
      messages: updatedMessages,
      generationSteps: updatedSteps,
    ));
  }

  void _onStreamErrorReceived(
    AssistantStreamErrorReceived event,
    Emitter<AssistantState> emit,
  ) {
    if (state is! AssistantLoaded) return;
    final currentState = state as AssistantLoaded;
    debugPrint(
      '[WS UI] stream error received activeJob=${currentState.activeJobId} '
      'isStreaming=${currentState.isStreaming} err=${event.error}',
    );
    _cancelWsTimeout();

    final hasConfirmCard = currentState.messages.any(
      (m) => m.intent == 'confirmation_required',
    );
    if (hasConfirmCard) {
      final cleanedMessages = currentState.messages
          .where((m) => !(m.role == MessageRole.assistant &&
              m.isStreaming &&
              m.content.isEmpty))
          .toList();
      emit(currentState.copyWith(
        messages: cleanedMessages,
        isLoading: false,
        isStreaming: false,
        awaitingBridging: false,
        streamingContent: '',
        generationSteps: [],
        progressStage: 'waiting_confirmation',
        progressMessage: '\u7b49\u5f85\u7528\u6237\u786e\u8ba4...',
        clearActiveJobId: true,
      ));
      bridgingTimeoutTimer?.cancel();
      bridgingTimeoutTimer = null;
      return;
    }

    final displayError = _sanitizeErrorForDisplay(event.error);

    final errorMessage = ChatMessage(
      id: DateTime.now().millisecondsSinceEpoch.toString(),
      sessionId: currentState.sessionId ?? '',
      role: MessageRole.assistant,
      content: displayError,
      createdAt: DateTime.now(),
    );

    final updatedMessages = _replaceOrAppendStreamingAssistantMessage(
      currentState.messages,
      errorMessage,
    );

    emit(currentState.copyWith(
      messages: updatedMessages,
      isLoading: false,
      isStreaming: false,
      awaitingBridging: false,
      streamingContent: '',
      generationSteps: [],
      error: displayError,
      progressStage: null,
      progressMessage: null,
      clearActiveJobId: true,
    ));
    bridgingTimeoutTimer?.cancel();
    bridgingTimeoutTimer = null;
    debugPrint(
      '[WS UI] stream error rendered activeJob=${currentState.activeJobId} '
      'displayErr=$displayError',
    );
  }

  void _onStreamToolExecutionReceived(
    AssistantStreamToolExecutionReceived event,
    Emitter<AssistantState> emit,
  ) {
    if (state is! AssistantLoaded) return;
    final currentState = state as AssistantLoaded;

    final fallbackKeyResults = event.keyResults ??
        (event.result is Map<String, dynamic> &&
                (event.result as Map<String, dynamic>).isNotEmpty
            ? event.result as Map<String, dynamic>
            : null);

    final newExecution = ToolExecutionStep(
      toolName: event.toolName,
      status: event.status,
      timestamp: DateTime.now(),
      result: event.result,
      executionId: event.executionId,
      keyResults: fallbackKeyResults,
      durationMs: event.durationMs,
      summary: event.summary,
      arguments: event.arguments,
    );

    final progressMessage = event.status == 'start'
        ? '\ud83d\udd27 \u6b63\u5728\u6267\u884c...'
        : event.status == 'progress'
            ? '\u23f3 ${event.summary ?? "\u5904\u7406\u4e2d..."}'
            : event.summary != null
                ? '\u2705 ${event.summary}'
                : '\u2705 \u5df2\u5b8c\u6210';

    final newProgressStep = ProgressStep(
      stage: 'tool_${event.status}',
      message: progressMessage,
      timestamp: DateTime.now(),
      data: event.result,
    );

    final currentSteps =
        List<GenerationStep>.from(currentState.generationSteps);

    if (event.status == 'start') {
      int existingIndex = -1;
      for (int i = currentSteps.length - 1; i >= 0; i--) {
        if (currentSteps[i] is ToolStep) {
          final ts = currentSteps[i] as ToolStep;
          if (ts.tool.toolName == event.toolName && ts.tool.status == 'start') {
            existingIndex = i;
            break;
          }
        }
      }

      if (existingIndex != -1) {
        currentSteps[existingIndex] = ToolStep(tool: newExecution);
      } else {
        currentSteps.add(ToolStep(tool: newExecution));
      }
    } else {
      int indexToUpdate = -1;
      for (int i = currentSteps.length - 1; i >= 0; i--) {
        if (currentSteps[i] is ToolStep) {
          final ts = currentSteps[i] as ToolStep;
          if (ts.tool.toolName == event.toolName) {
            indexToUpdate = i;
            break;
          }
        }
      }

      if (indexToUpdate != -1) {
        currentSteps[indexToUpdate] = ToolStep(tool: newExecution);
      } else {
        currentSteps.add(ToolStep(tool: newExecution));
      }
    }

    final updatedMessages = _updateLastStreamingAssistantMessage(
      currentState.messages,
      (message) => message.copyWith(generationSteps: currentSteps),
    );

    emit(currentState.copyWith(
      messages: updatedMessages,
      generationSteps: currentSteps,
      progressStage: 'tool_${event.status}',
      progressMessage: progressMessage,
      progressHistory: [...currentState.progressHistory, newProgressStep],
    ));
  }

  void _onStreamToolProgressReceived(
    AssistantStreamToolProgressReceived event,
    Emitter<AssistantState> emit,
  ) {
    if (state is! AssistantLoaded) return;
    final currentState = state as AssistantLoaded;

    final currentSteps =
        List<GenerationStep>.from(currentState.generationSteps);

    int targetIndex = -1;
    for (int i = currentSteps.length - 1; i >= 0; i--) {
      if (currentSteps[i] is ToolStep) {
        final ts = currentSteps[i] as ToolStep;
        if (ts.tool.toolName == event.toolName && ts.tool.status == 'start') {
          targetIndex = i;
          break;
        }
      }
    }

    if (targetIndex == -1) return;

    final existingStep = currentSteps[targetIndex] as ToolStep;
    final updatedTool = existingStep.tool.copyWith(
      progressLog: [...existingStep.tool.progressLog, event.message],
    );
    currentSteps[targetIndex] = ToolStep(tool: updatedTool);

    final updatedMessages = _updateLastStreamingAssistantMessage(
      currentState.messages,
      (message) => message.copyWith(generationSteps: currentSteps),
    );

    emit(currentState.copyWith(
      messages: updatedMessages,
      generationSteps: currentSteps,
    ));
  }

  void _onStreamConfirmCardReceived(
    AssistantStreamConfirmCardReceived event,
    Emitter<AssistantState> emit,
  ) {
    if (state is! AssistantLoaded) return;
    final currentState = state as AssistantLoaded;

    final confirmMessage = ChatMessage(
      id: DateTime.now().millisecondsSinceEpoch.toString(),
      sessionId: currentState.sessionId ?? '',
      role: MessageRole.assistant,
      content: '',
      intent: 'confirmation_required',
      data: event.payload,
      createdAt: DateTime.now(),
    );

    final updatedMessages = _replaceOrAppendStreamingAssistantMessage(
      currentState.messages,
      confirmMessage,
    );

    emit(currentState.copyWith(
      messages: updatedMessages,
      isStreaming: false,
      progressStage: 'waiting_confirmation',
      progressMessage: '\u7b49\u5f85\u7528\u6237\u786e\u8ba4...',
    ));
  }

  void _onStreamAskUserQuestionReceived(
    AssistantStreamAskUserQuestionReceived event,
    Emitter<AssistantState> emit,
  ) {
    if (state is! AssistantLoaded) return;
    final currentState = state as AssistantLoaded;

    final questionMessage = ChatMessage(
      id: DateTime.now().millisecondsSinceEpoch.toString(),
      sessionId: currentState.sessionId ?? '',
      role: MessageRole.assistant,
      content: '',
      intent: 'ask_user_question',
      data: event.payload,
      createdAt: DateTime.now(),
    );

    final updatedMessages = _replaceOrAppendStreamingAssistantMessage(
      currentState.messages,
      questionMessage,
    );

    emit(currentState.copyWith(
      messages: updatedMessages,
      isStreaming: false,
      progressStage: 'waiting_answer',
      progressMessage: '\u7b49\u5f85\u7528\u6237\u56de\u7b54...',
    ));
  }

  void _onRouteInfoReceived(
    AssistantRouteInfoReceived event,
    Emitter<AssistantState> emit,
  ) {
    if (state is! AssistantLoaded) return;
    final currentState = state as AssistantLoaded;

    final routeMessages = {
      'fast': '\u5feb\u901f\u54cd\u5e94\u4e2d...',
      'slow': '\u6b63\u5728\u6df1\u5ea6\u601d\u8003...',
      'hybrid': '\u5feb\u901f\u54cd\u5e94 + \u6df1\u5ea6\u5206\u6790...',
    };

    emit(currentState.copyWith(
      progressStage: 'route',
      progressMessage:
          routeMessages[event.routeType] ?? '\u5904\u7406\u4e2d...',
    ));
  }

  void _onTaskQueued(
    AssistantTaskQueued event,
    Emitter<AssistantState> emit,
  ) {
    if (state is! AssistantLoaded) return;
    final currentState = state as AssistantLoaded;
    emit(currentState.copyWith(
      activeJobId: event.jobId,
      progressStage: 'queued',
      progressMessage: '\u6b63\u5728\u6df1\u5ea6\u601d\u8003\u4e2d...',
    ));
    _scheduleWsTimeout(_wsStartTimeout);
  }

  void _onBackgroundJobStarted(
    AssistantBackgroundJobStarted event,
    Emitter<AssistantState> emit,
  ) {
    if (state is! AssistantLoaded) return;
    final currentState = state as AssistantLoaded;
    emit(currentState.copyWith(
      activeJobId: event.jobId,
      progressStage: 'background_job',
      progressMessage:
          '\u6b63\u5728\u601d\u8003\u662f\u5426\u8fd8\u6709\u5173\u8054\u4e8b\u9879...',
    ));
    _scheduleWsTimeout(_wsStartTimeout);
  }

  void _onSlowPathResultReceived(
    AssistantSlowPathResultReceived event,
    Emitter<AssistantState> emit,
  ) {
    if (state is! AssistantLoaded) return;
    var currentState = state as AssistantLoaded;
    final wsEvent = event.event;
    final isHybridFastLegDone =
        wsEvent.type == StreamEventType.done && wsEvent.routeType == 'hybrid';

    // Filter by activeJobId when in WS mode: ignore events for stale jobs
    if (AssistantBloc.useWebSocketChat && currentState.activeJobId != null) {
      if (wsEvent.jobId != null && wsEvent.jobId != currentState.activeJobId) {
        // Hybrid handoff and voice-chat-started events are allowed to switch
        // the active job_id from a previous (stale) job to the new one.
        if (wsEvent.type == StreamEventType.backgroundJob ||
            wsEvent.type == StreamEventType.voiceChatStarted ||
            isHybridFastLegDone) {
          // pass through
        } else {
          debugPrint(
            '[WS FILTER] drop stale event type=${wsEvent.type} '
            'eventJob=${wsEvent.jobId} activeJob=${currentState.activeJobId} '
            'seq=${wsEvent.seq}',
          );
          return; // Stale job event, ignore
        }
      }
    }

    // Track last sequence number for resume capability
    if (wsEvent.seq != null) {
      webSocketService?.updateLastSeq(wsEvent.seq!);
    }

    if (wsEvent.type == StreamEventType.done ||
        wsEvent.type == StreamEventType.error) {
      debugPrint(
        '[WS FLOW] terminal event type=${wsEvent.type} job=${wsEvent.jobId} '
        'activeJob=${currentState.activeJobId} seq=${wsEvent.seq}',
      );
      _cancelWsTimeout();
      // Clear active job on WS service
      if (AssistantBloc.useWebSocketChat) {
        if (!isHybridFastLegDone) {
          webSocketService?.clearActiveJob();
        }
      }
      if (isHybridFastLegDone) {
        _scheduleWsTimeout(_wsStartTimeout);
      }
    } else {
      _scheduleWsTimeout(_wsIdleTimeout);
    }

    const backgroundStatusMessage =
        '\u6b63\u5728\u601d\u8003\u662f\u5426\u8fd8\u6709\u5173\u8054\u4e8b\u9879...';

    // Clean up the background placeholder on the first real event from the
    // background worker.  This MUST run BEFORE the suppression check so that
    // progressStage transitions from 'background_job' → 'processing',
    // allowing subsequent streaming events to pass through.
    final isRealEvent = const {
      StreamEventType.content,
      StreamEventType.thinking,
      StreamEventType.thinkingStart,
      StreamEventType.toolExecution,
      StreamEventType.toolResult,
      StreamEventType.toolStart,
    }.contains(wsEvent.type);

    if (isRealEvent &&
        currentState.generationSteps.any(
          (s) => s is ThinkingStep && s.content == backgroundStatusMessage,
        )) {
      final cleanedSteps = currentState.generationSteps
          .where((s) =>
              !(s is ThinkingStep && s.content == backgroundStatusMessage))
          .toList();
      final cleanedMessages = _updateLastStreamingAssistantMessage(
        currentState.messages,
        (message) => message.copyWith(generationSteps: cleanedSteps),
      );
      emit(currentState.copyWith(
        messages: cleanedMessages,
        generationSteps: cleanedSteps,
        progressStage: 'processing',
        progressMessage: '\u6b63\u5728\u5206\u6790\u5173\u8054\u4fe1\u606f...',
      ));
      currentState = state as AssistantLoaded;
    }

    // Determine if we are still in the background waiting phase.
    // Only check progressStage and the placeholder ThinkingStep — do NOT
    // check progressHistory (it is a permanent record and would make
    // suppression permanent, blocking all background streaming).
    final isBackgroundFlow = currentState.progressStage == 'background_job' ||
        currentState.generationSteps.any(
          (s) => s is ThinkingStep && s.content == backgroundStatusMessage,
        );
    final suppressBackgroundIntermediateEvents = <StreamEventType>{
      StreamEventType.content,
      StreamEventType.thinking,
      StreamEventType.thinkingStart,
      StreamEventType.thinkingEnd,
      StreamEventType.toolExecution,
      StreamEventType.toolResult,
      StreamEventType.toolProgress,
    };

    if (isBackgroundFlow &&
        suppressBackgroundIntermediateEvents.contains(wsEvent.type)) {
      return;
    }

    switch (wsEvent.type) {
      case StreamEventType.backgroundJob:
        final nextJobId = wsEvent.jobId;
        if (nextJobId != null && nextJobId.isNotEmpty) {
          webSocketService?.setActiveJob(nextJobId);
        }
        add(AssistantBackgroundJobStarted(nextJobId));
        break;
      case StreamEventType.content:
        if (wsEvent.content != null && wsEvent.content!.isNotEmpty) {
          final newContent = currentState.streamingContent + wsEvent.content!;

          final updatedSteps =
              List<GenerationStep>.from(currentState.generationSteps);
          if (updatedSteps.isNotEmpty && updatedSteps.last is ContentStep) {
            final lastStep = updatedSteps.last as ContentStep;
            updatedSteps[updatedSteps.length - 1] =
                ContentStep(content: lastStep.content + wsEvent.content!);
          } else {
            updatedSteps.add(ContentStep(content: wsEvent.content!));
          }

          final messagesWithPlaceholder = _ensureStreamingMessage(currentState);
          final updatedMessages = _updateLastStreamingAssistantMessage(
            messagesWithPlaceholder,
            (message) => message.copyWith(
              content: newContent,
              generationSteps: updatedSteps,
            ),
          );

          emit(currentState.copyWith(
            messages: updatedMessages,
            streamingContent: newContent,
            generationSteps: updatedSteps,
            isStreaming: true,
          ));
          // After receiving content, use shorter timeout — if the done event
          // is lost we recover in 15s instead of 120s.
          _scheduleWsTimeout(_wsCompleteTimeout);
        }
        break;
      case StreamEventType.done:
        if (wsEvent.asyncSource != null) {
          // Async push message — insert directly into message list.
          final asyncMessage = ChatMessage(
            id: wsEvent.messageId ??
                DateTime.now().millisecondsSinceEpoch.toString(),
            sessionId: currentState.sessionId ?? '',
            role: MessageRole.assistant,
            content: wsEvent.content ?? '',
            intent: wsEvent.intent,
            data: wsEvent.data,
            cardType: wsEvent.cardType,
            asyncSource: wsEvent.asyncSource,
            createdAt: DateTime.now(),
          );
          emit(currentState.copyWith(
            messages: [...currentState.messages, asyncMessage],
            isStreaming: false,
            clearActiveJobId: true,
          ));
        } else {
          // Reconcile thinking: if the done event carries full thinking,
          // replace the (possibly truncated) streaming thinking with it.
          if (!isBackgroundFlow &&
              wsEvent.fullThinking != null &&
              wsEvent.fullThinking!.isNotEmpty) {
            final reconciledSteps = currentState.generationSteps.map((s) {
              if (s is ThinkingStep) {
                return ThinkingStep(
                  content: wsEvent.fullThinking!,
                  isComplete: true,
                );
              }
              return s;
            }).toList();
            emit(currentState.copyWith(
              clearActiveJobId: !isHybridFastLegDone,
              generationSteps: reconciledSteps,
            ));
          } else {
            emit(currentState.copyWith(clearActiveJobId: !isHybridFastLegDone));
          }
          add(AssistantStreamCompleted(
            messageId: wsEvent.messageId,
            intent: wsEvent.intent,
            data: wsEvent.data,
            cardType: wsEvent.cardType,
            quickActions: wsEvent.quickActions,
            content: wsEvent.content,
            clearActiveJobId: !isHybridFastLegDone,
          ));
        }
        break;
      case StreamEventType.error:
        debugPrint(
          '[WS FLOW] error event dispatch job=${wsEvent.jobId} '
          'activeJob=${currentState.activeJobId} seq=${wsEvent.seq} '
          'message=${wsEvent.message}',
        );
        emit(currentState.copyWith(clearActiveJobId: true));
        add(AssistantStreamErrorReceived(
          wsEvent.message ?? '\u540e\u53f0\u5904\u7406\u5931\u8d25',
        ));
        break;
      case StreamEventType.progress:
        add(AssistantStreamProgressReceived(
          wsEvent.stage ?? 'processing',
          wsEvent.message ?? '\u5904\u7406\u4e2d...',
        ));
        break;
      case StreamEventType.confirmCard:
        if (wsEvent.confirmCardPayload != null) {
          add(AssistantStreamConfirmCardReceived(wsEvent.confirmCardPayload!));
        }
        break;
      case StreamEventType.askUserQuestion:
        if (wsEvent.askUserQuestionPayload != null) {
          add(AssistantStreamAskUserQuestionReceived(
              wsEvent.askUserQuestionPayload!));
        }
        break;
      case StreamEventType.toolExecution:
      case StreamEventType.toolResult:
        final msgsForTool = _ensureStreamingMessage(currentState);
        if (msgsForTool.length != currentState.messages.length) {
          emit(currentState.copyWith(
            messages: msgsForTool,
            isStreaming: true,
          ));
        }
        add(AssistantStreamToolExecutionReceived(
          toolName: wsEvent.toolName ?? 'unknown',
          status: wsEvent.toolStatus ?? 'start',
          result: wsEvent.toolResult,
          executionId: wsEvent.toolExecutionId,
          summary: wsEvent.toolSummary ?? wsEvent.message,
          keyResults: wsEvent.toolKeyResults,
          durationMs: wsEvent.toolDurationMs,
          arguments: wsEvent.toolArguments,
        ));
        break;
      case StreamEventType.toolProgress:
        final msgsForToolProgress = _ensureStreamingMessage(currentState);
        if (msgsForToolProgress.length != currentState.messages.length) {
          emit(currentState.copyWith(
            messages: msgsForToolProgress,
            isStreaming: true,
          ));
        }
        add(AssistantStreamToolProgressReceived(
          toolName: wsEvent.toolName ?? 'unknown',
          message:
              wsEvent.toolSummary ?? wsEvent.message ?? '\u5904\u7406\u4e2d...',
        ));
        break;
      case StreamEventType.thinking:
        final msgsForThinking = _ensureStreamingMessage(currentState);
        if (msgsForThinking.length != currentState.messages.length) {
          emit(currentState.copyWith(
            messages: msgsForThinking,
            isStreaming: true,
          ));
        }
        if (wsEvent.content != null && wsEvent.content!.isNotEmpty) {
          add(AssistantStreamThinkingReceived(wsEvent.content!));
        }
        break;
      case StreamEventType.thinkingStart:
        final msgsForThinkStart = _ensureStreamingMessage(currentState);
        if (msgsForThinkStart.length != currentState.messages.length) {
          emit(currentState.copyWith(
            messages: msgsForThinkStart,
            isStreaming: true,
          ));
        }
        add(AssistantStreamThinkingStarted(content: wsEvent.content ?? ''));
        break;
      case StreamEventType.thinkingEnd:
        if (currentState.generationSteps.isNotEmpty &&
            currentState.generationSteps.last is ThinkingStep) {
          final steps = List<GenerationStep>.from(currentState.generationSteps);
          final lastThinking = steps.last as ThinkingStep;
          steps[steps.length - 1] = lastThinking.copyWith(isComplete: true);
          final msgsForThinkEnd = _updateLastStreamingAssistantMessage(
            currentState.messages,
            (message) => message.copyWith(generationSteps: steps),
          );
          emit(currentState.copyWith(
            messages: msgsForThinkEnd,
            generationSteps: steps,
          ));
        }
        break;
      case StreamEventType.agenticIteration:
        add(AssistantStreamProgressReceived(
          'agentic_iteration',
          wsEvent.message ??
              '\u6b63\u5728\u8fdb\u884c\u7b2c${wsEvent.agenticIteration}\u8f6e\u601d\u8003...',
        ));
        break;
      case StreamEventType.partialContent:
        if (wsEvent.content != null && wsEvent.content!.isNotEmpty) {
          add(AssistantPartialContentReceived(
            chunk: wsEvent.content!,
            generationId: wsEvent.generationId,
            interruptedBy: wsEvent.interruptedBy,
          ));
        }
        break;
      case StreamEventType.bridging:
        if (wsEvent.bridgingType != null) {
          add(AssistantBridgingReceived(
            bridgingType: wsEvent.bridgingType!,
            generationId: wsEvent.generationId,
          ));
        }
        break;
      case StreamEventType.generationState:
        if (wsEvent.generationStateAction != null) {
          add(AssistantGenerationStateReceived(
            action: wsEvent.generationStateAction!,
            generationId: wsEvent.generationId,
          ));
        }
        break;
      case StreamEventType.sidekickInsight:
        add(AssistantSidekickInsightReceived(wsEvent.data ?? const {}));
        break;
      case StreamEventType.voiceTranscription:
        // V-M-10: Robust partial detection — partial only if explicitly
        // marked partial AND not marked as final.
        add(VoiceStreamTranscriptionReceived(
          text: wsEvent.content ?? '',
          isPartial: wsEvent.data?['partial'] == true &&
              wsEvent.data?['is_final'] != true,
          isCancelled: wsEvent.data?['cancelled'] == true,
        ));
        break;
      case StreamEventType.voiceChatStarted:
        // V-M-2: Cancel voice response timeout — backend has responded.
        (this as AssistantBloc)._voiceResponseTimeoutTimer?.cancel();
        (this as AssistantBloc)._voiceResponseTimeoutTimer = null;
        // Voice-triggered chat job dispatched by backend.  Update activeJobId
        // so subsequent AI response events pass the stale-job filter.
        final voiceJobId = wsEvent.jobId;
        if (voiceJobId != null && voiceJobId.isNotEmpty) {
          webSocketService?.setActiveJob(voiceJobId);
          final vs = state;
          if (vs is AssistantLoaded) {
            emit(vs.copyWith(activeJobId: voiceJobId));
          }
        }
        final voiceSessionId = wsEvent.sessionId;
        if (voiceSessionId != null && voiceSessionId.isNotEmpty) {
          add(AssistantStreamSessionReceived(voiceSessionId));
        }
        break;
      case StreamEventType.memoryExtracted:
        final p = wsEvent.data ?? const {};
        add(MemoryExtractedReceived(
          summary: p['summary'] as String? ?? 'memory',
          entities: p['entities'] is Map<String, dynamic>
              ? p['entities'] as Map<String, dynamic>
              : const {},
          mentionedPersons: (p['mentioned_persons'] as List<dynamic>?)
                  ?.cast<String>() ??
              const [],
        ));
        break;
      case StreamEventType.voiceError:
        debugPrint('[WS] voice_error: ${wsEvent.message}');
        add(const VoiceStreamCancelRequested());
        // M-5: Surface voice error to the user via error state
        final voiceErrorMsg = wsEvent.message ?? '语音识别出错，请重试';
        add(AssistantStreamErrorReceived(voiceErrorMsg));
        break;
      default:
        break;
    }
  }

  // ── Full-duplex event handlers ──────────────────────────────────────

  void _onPartialContentReceived(
    AssistantPartialContentReceived event,
    Emitter<AssistantState> emit,
  ) {
    if (state is! AssistantLoaded) return;
    final currentState = state as AssistantLoaded;

    // Backend sends full accumulated text, not a delta chunk.
    // Use replacement instead of accumulation to avoid content duplication.
    final newContent = event.chunk;

    final updatedSteps =
        List<GenerationStep>.from(currentState.generationSteps);
    if (updatedSteps.isNotEmpty && updatedSteps.last is ContentStep) {
      updatedSteps[updatedSteps.length - 1] = ContentStep(content: newContent);
    } else {
      updatedSteps.add(ContentStep(content: newContent));
    }

    final messagesWithPlaceholder = _ensureStreamingMessage(currentState);
    final updatedMessages = _updateLastStreamingAssistantMessage(
      messagesWithPlaceholder,
      (message) => message.copyWith(
        content: newContent,
        generationSteps: updatedSteps,
        isPartial: true,
        generationId: event.generationId,
      ),
    );

    emit(currentState.copyWith(
      messages: updatedMessages,
      streamingContent: newContent,
      generationSteps: updatedSteps,
      isStreaming: true,
      hasPartialMessage: true,
      currentGenerationId: event.generationId,
      interruptionType: event.interruptedBy,
    ));
  }

  void _onBridgingReceived(
    AssistantBridgingReceived event,
    Emitter<AssistantState> emit,
  ) {
    if (state is! AssistantLoaded) return;
    final currentState = state as AssistantLoaded;

    // Dedup guard: skip already-processed bridging events (PubSub at-least-once delivery)
    final bridgingType = event.bridgingType;
    final genId = event.generationId ?? '';
    if (genId.isEmpty) {
      debugPrint('[WARN] Bridging event missing generationId, using fallback handler');
      // Fall through to generic bridging handler below instead of returning
    } else {
      final bridgingId = '$bridgingType:$genId';
      if (processedBridgingIds.contains(bridgingId)) {
        return;
      }
      processedBridgingIds.add(bridgingId);
      // Dart's default Set (LinkedHashSet) maintains insertion order,
      // so .first returns the oldest entry for FIFO eviction.
      if (processedBridgingIds.length > maxBridgingIds) {
        processedBridgingIds.remove(processedBridgingIds.first);
      }
    }

    if (genId.isNotEmpty && event.bridgingType == 'correction') {
      // CORRECTION: mark current partial as superseded, prepare for replacement
      final updatedMessages = [
        ...currentState.messages.map((msg) {
          if (msg.role == MessageRole.assistant &&
              msg.isStreaming &&
              msg.isPartial) {
            return msg.copyWith(
              isStreaming: false,
              isPartial: true,
              isSuperseded: true,
              signalType: 'correction',
            );
          }
          return msg;
        }),
        // New streaming placeholder for the corrected response
        ChatMessage(
          id: DateTime.now().millisecondsSinceEpoch.toString(),
          sessionId: currentState.sessionId ?? '',
          role: MessageRole.assistant,
          content: '',
          generationSteps: const [],
          isStreaming: true,
          generationId: event.generationId,
          continuesFrom: currentState.currentGenerationId,
          createdAt: DateTime.now(),
        ),
      ];

      emit(currentState.copyWith(
        messages: updatedMessages,
        streamingContent: '',
        generationSteps: [],
        hasPartialMessage: false,
        interruptionType: 'correction',
        currentGenerationId: event.generationId,
        awaitingBridging: false,
      ));
      bridgingTimeoutTimer?.cancel();
      bridgingTimeoutTimer = null;
    } else if (genId.isNotEmpty && event.bridgingType == 'digression') {
      // DIGRESSION: finalize current partial as-is, start new bubble
      final updatedMessages = [
        ...currentState.messages.map((msg) {
          if (msg.role == MessageRole.assistant &&
              msg.isStreaming &&
              msg.isPartial) {
            return msg.copyWith(
              isStreaming: false,
              isPartial: true,
              signalType: 'digression',
            );
          }
          return msg;
        }),
        // New streaming placeholder for the digression response
        ChatMessage(
          id: DateTime.now().millisecondsSinceEpoch.toString(),
          sessionId: currentState.sessionId ?? '',
          role: MessageRole.assistant,
          content: '',
          generationSteps: const [],
          isStreaming: true,
          generationId: event.generationId,
          continuesFrom: currentState.currentGenerationId,
          createdAt: DateTime.now(),
        ),
      ];

      emit(currentState.copyWith(
        messages: updatedMessages,
        streamingContent: '',
        generationSteps: [],
        hasPartialMessage: false,
        interruptionType: 'digression',
        currentGenerationId: event.generationId,
        awaitingBridging: false,
      ));
      bridgingTimeoutTimer?.cancel();
      bridgingTimeoutTimer = null;
    } else {
      // Other bridge types (confirm, etc.): update generation tracking
      emit(currentState.copyWith(
        currentGenerationId: event.generationId,
        hasPartialMessage: false,
        clearInterruptionType: true,
      ));
    }
  }

  void _onGenerationStateReceived(
    AssistantGenerationStateReceived event,
    Emitter<AssistantState> emit,
  ) {
    if (state is! AssistantLoaded) return;
    final currentState = state as AssistantLoaded;

    if (event.action == 'cancel') {
      // Cancel: keep partial content as-is with lowered weight
      final updatedMessages = currentState.messages.map((msg) {
        if (msg.role == MessageRole.assistant && msg.isStreaming) {
          return msg.copyWith(
            isStreaming: false,
            isPartial: msg.content.isNotEmpty,
            signalType: 'cancel',
          );
        }
        return msg;
      }).toList();

      emit(currentState.copyWith(
        messages: updatedMessages,
        isStreaming: false,
        streamingContent: '',
        generationSteps: [],
        hasPartialMessage: false,
        awaitingBridging: false,
        clearInterruptionType: true,
        clearCurrentGenerationId: true,
        clearActiveJobId: true,
      ));
      bridgingTimeoutTimer?.cancel();
      bridgingTimeoutTimer = null;
    } else if (event.action == 'interrupt') {
      // Interrupt: show transient loading state while bridging follows
      emit(currentState.copyWith(
        interruptionType: 'interrupt',
        progressStage: 'interrupting',
        progressMessage: '\u6b63\u5728\u8c03\u6574\u56de\u590d...',
      ));
    } else if (event.action == 'resume') {
      // Resume: clear the interrupt transient state
      emit(currentState.copyWith(
        clearInterruptionType: true,
        progressStage: 'processing',
        progressMessage: '\u7ee7\u7eed\u56de\u590d\u4e2d...',
      ));
    }
  }

  void _onSidekickInsightReceived(
    AssistantSidekickInsightReceived event,
    Emitter<AssistantState> emit,
  ) {
    if (state is! AssistantLoaded) return;
    final currentState = state as AssistantLoaded;

    final insightMessage = ChatMessage(
      id: DateTime.now().millisecondsSinceEpoch.toString(),
      sessionId: currentState.sessionId ?? '',
      role: MessageRole.assistant,
      content: event.payload['content'] as String? ?? '',
      intent: 'sidekick_insight',
      data: event.payload,
      cardType: 'sidekick_insight',
      createdAt: DateTime.now(),
    );

    emit(currentState.copyWith(
      messages: [...currentState.messages, insightMessage],
    ));
  }

  void _onSignalHintReceived(
    AssistantSignalHintReceived event,
    Emitter<AssistantState> emit,
  ) {
    if (state is! AssistantLoaded) return;
    final currentState = state as AssistantLoaded;
    emit(currentState.copyWith(
      signalHint: event.hint,
      signalHintType: event.signalType,
    ));

    // Cancel previous timer if any
    signalHintTimer?.cancel();
    // Interrupting signals (correction/digression) stay longer for visibility
    final isInterrupting =
        event.signalType == 'correction' || event.signalType == 'digression';
    final dismissDuration =
        Duration(seconds: isInterrupting ? 3 : 2);
    signalHintTimer = Timer(dismissDuration, () {
      if (!isClosed) {
        add(const AssistantSignalHintDismissed());
      }
    });
  }

  void _onSignalHintDismissed(
    AssistantSignalHintDismissed event,
    Emitter<AssistantState> emit,
  ) {
    if (state is! AssistantLoaded) return;
    final currentState = state as AssistantLoaded;
    emit(currentState.copyWith(
      clearSignalHint: true,
      clearSignalHintType: true,
    ));
  }

  List<ChatMessage> _ensureStreamingMessage(AssistantLoaded st) {
    if (st.messages.any((m) => m.isStreaming)) return st.messages;
    return [
      ...st.messages,
      ChatMessage(
        id: 'ws-streaming',
        sessionId: st.sessionId ?? '',
        role: MessageRole.assistant,
        content: '',
        generationSteps: const [],
        isStreaming: true,
        createdAt: DateTime.now(),
      ),
    ];
  }

  // Shared helpers
  static const Duration _wsStartTimeout = Duration(seconds: 120);
  static const Duration _wsIdleTimeout = Duration(seconds: 120);
  static const Duration _wsCompleteTimeout = Duration(seconds: 15);

  String? _extractThinkingContent(List<GenerationStep> steps) {
    if (steps.isEmpty) return null;
    final content =
        steps.whereType<ThinkingStep>().map((s) => s.content).join('\n\n');
    return content.isEmpty ? null : content;
  }

  List<ChatMessage> _updateLastStreamingAssistantMessage(
    List<ChatMessage> messages,
    ChatMessage Function(ChatMessage) update,
  ) {
    for (int i = messages.length - 1; i >= 0; i--) {
      final message = messages[i];
      if (message.role == MessageRole.assistant && message.isStreaming) {
        final updated = update(message);
        final updatedMessages = List<ChatMessage>.from(messages);
        updatedMessages[i] = updated;
        return updatedMessages;
      }
    }
    return messages;
  }

  List<ChatMessage> _replaceOrAppendStreamingAssistantMessage(
    List<ChatMessage> messages,
    ChatMessage replacement,
  ) {
    for (int i = messages.length - 1; i >= 0; i--) {
      final message = messages[i];
      if (message.role == MessageRole.assistant && message.isStreaming) {
        final updatedMessages = List<ChatMessage>.from(messages);
        updatedMessages[i] = replacement;
        return updatedMessages;
      }
    }
    return [...messages, replacement];
  }

  void _scheduleWsTimeout(Duration duration) {
    final currentState = state;
    if (currentState is! AssistantLoaded || currentState.activeJobId == null) {
      _cancelWsTimeout();
      return;
    }
    debugPrint(
      '[WS TIMEOUT] schedule durationMs=${duration.inMilliseconds} '
      'activeJob=${currentState.activeJobId} progress=${currentState.progressStage}',
    );
    wsIdleTimer?.cancel();
    wsIdleTimer = Timer(duration, () {
      if (isClosed) return;
      final latestState = state;
      if (latestState is! AssistantLoaded) return;
      if (latestState.activeJobId == null) return;
      debugPrint(
        '[WS TIMEOUT] fired activeJob=${latestState.activeJobId} '
        'streamingLen=${latestState.streamingContent.length} '
        'progress=${latestState.progressStage}',
      );
      add(AssistantStreamCompleted(
        content: latestState.streamingContent,
        clearActiveJobId: true,
      ));
    });
  }

  void _cancelWsTimeout() {
    if (wsIdleTimer != null) {
      final currentState = state;
      if (currentState is AssistantLoaded) {
        debugPrint(
          '[WS TIMEOUT] cancel activeJob=${currentState.activeJobId} '
          'progress=${currentState.progressStage}',
        );
      } else {
        debugPrint('[WS TIMEOUT] cancel state=${currentState.runtimeType}');
      }
    }
    wsIdleTimer?.cancel();
    wsIdleTimer = null;
  }
}
