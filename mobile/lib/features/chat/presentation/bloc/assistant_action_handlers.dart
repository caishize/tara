part of 'assistant_bloc.dart';

/// Message action handlers extracted from AssistantBloc.
///
/// Handles: regenerate, edit, dismiss/act on suggestion,
/// assign task, confirm travel plan, sync pending actions.
mixin AssistantActionHandlers
    on Bloc<AssistantEvent, AssistantState>, AssistantStreamHandlers {
  PendingActionDatasource? get pendingActionDatasource;
  static final RegExp _uuidRegex = RegExp(
    r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$',
  );

  bool _isServerMessageId(String value) => _uuidRegex.hasMatch(value);

  Future<void> _onRegenerateMessage(
    AssistantRegenerateMessage event,
    Emitter<AssistantState> emit,
  ) async {
    if (state is! AssistantLoaded) return;
    final currentState = state as AssistantLoaded;
    if (currentState.sessionId == null) return;

    final messageIndex =
        currentState.messages.indexWhere((m) => m.id == event.messageId);
    if (messageIndex == -1) return;
    if (!_isServerMessageId(event.messageId)) {
      add(const AssistantStreamErrorReceived('当前消息暂不支持重新生成，请重新发送一条新消息'));
      return;
    }

    // Mark old message as superseded, add new streaming placeholder after it
    final updatedMessages = List<ChatMessage>.from(currentState.messages);
    updatedMessages[messageIndex] = updatedMessages[messageIndex].copyWith(
      isSuperseded: true,
    );

    final newStreamingMessage = ChatMessage(
      id: DateTime.now().millisecondsSinceEpoch.toString(),
      sessionId: currentState.sessionId!,
      role: MessageRole.assistant,
      content: '',
      isStreaming: true,
      generationSteps: const [],
      createdAt: DateTime.now(),
    );
    updatedMessages.insert(messageIndex + 1, newStreamingMessage);

    emit(currentState.copyWith(
      messages: updatedMessages,
      isStreaming: true,
      streamingContent: '',
      generationSteps: [],
      error: null,
    ));

    // WebSocket mode: POST /chat/regenerate, results via WS
    final result = await repository.regenerateMessageWs(
      sessionId: currentState.sessionId!,
      messageId: event.messageId,
    );

    result.fold(
      (failure) {
        add(AssistantStreamErrorReceived(failure.message));
      },
      (response) {
        final jobId = response['job_id'] as String?;
        if (jobId != null) {
          webSocketService?.setActiveJob(jobId);
          final latestState = state;
          if (latestState is AssistantLoaded) {
            emit(latestState.copyWith(activeJobId: jobId));
          }
          final routeType = response['route_type'] as String?;
          if (routeType == 'slow') {
            add(AssistantTaskQueued(jobId));
          } else if (routeType == 'hybrid') {
            add(const AssistantRouteInfoReceived('hybrid'));
          } else {
            add(const AssistantRouteInfoReceived('fast'));
          }
        }
        // Results will arrive via existing _wsSubscription
      },
    );
  }

  Future<void> _onEditMessage(
    AssistantEditMessage event,
    Emitter<AssistantState> emit,
  ) async {
    if (state is! AssistantLoaded) return;
    final currentState = state as AssistantLoaded;
    if (currentState.sessionId == null) return;

    final messageIndex =
        currentState.messages.indexWhere((m) => m.id == event.messageId);
    if (messageIndex == -1) return;
    if (!_isServerMessageId(event.messageId)) {
      add(const AssistantStreamErrorReceived('当前消息暂不支持编辑，请重新发送一条新消息'));
      return;
    }

    final editedMessage = currentState.messages[messageIndex].copyWith(
      content: event.newContent,
      isSuperseded: false,
      createdAt: DateTime.now(),
    );
    final updatedMessages = <ChatMessage>[
      ...currentState.messages.take(messageIndex),
      editedMessage,
      ChatMessage(
        id: DateTime.now().millisecondsSinceEpoch.toString(),
        sessionId: currentState.sessionId!,
        role: MessageRole.assistant,
        content: '',
        isStreaming: true,
        generationSteps: const [],
        createdAt: DateTime.now(),
      ),
    ];

    emit(currentState.copyWith(
      messages: updatedMessages,
      isStreaming: true,
      streamingContent: '',
      generationSteps: [],
      error: null,
      progressHistory: [],
      progressStage: null,
      progressMessage: null,
    ));

    await for (final streamEvent in repository.streamEditMessage(
      sessionId: currentState.sessionId!,
      messageId: event.messageId,
      newContent: event.newContent,
    )) {
      switch (streamEvent.type) {
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
            streamEvent.message ?? '编辑失败，请稍后重试',
          ));
          break;
        default:
          break;
      }
    }
  }

  Future<void> _onDismissSuggestion(
    AssistantDismissSuggestion event,
    Emitter<AssistantState> emit,
  ) async {
    final result = await repository.dismissSuggestion(event.suggestionId);
    result.fold(
      (failure) {
        if (state is AssistantLoaded) {
          emit((state as AssistantLoaded).copyWith(error: failure.message));
        }
      },
      (_) {},
    );
  }

  Future<void> _onActOnSuggestion(
    AssistantActOnSuggestion event,
    Emitter<AssistantState> emit,
  ) async {
    if (state is! AssistantLoaded) return;
    final currentState = state as AssistantLoaded;

    emit(currentState.copyWith(isLoading: true, error: null));

    final result = await repository.actOnSuggestion(event.suggestionId);

    result.fold(
      (failure) => emit(currentState.copyWith(
        isLoading: false,
        error: failure.message,
      )),
      (actionResult) {
        emit(currentState.copyWith(isLoading: false));
      },
    );
  }

  Future<void> _onAssignTask(
    AssistantAssignTask event,
    Emitter<AssistantState> emit,
  ) async {
    if (state is! AssistantLoaded) return;
    final currentState = state as AssistantLoaded;

    emit(currentState.copyWith(isLoading: true, error: null));

    final result = await repository.assignTask(event.taskId, event.assigneeId);

    result.fold(
      (failure) => emit(currentState.copyWith(
        isLoading: false,
        error: failure.message,
      )),
      (task) {
        emit(currentState.copyWith(isLoading: false));
      },
    );
  }

  Future<void> _onConfirmTravelPlan(
    AssistantConfirmTravelPlan event,
    Emitter<AssistantState> emit,
  ) async {
    if (state is! AssistantLoaded) {
      event.onComplete?.call(null);
      return;
    }
    final currentState = state as AssistantLoaded;

    try {
      final result = await repository.confirmTravelPlan(
        event.messageId,
        event.planData,
      );

      result.fold(
        (failure) {
          event.onComplete?.call(null);
        },
        (planId) {
          final updatedMessages = currentState.messages.map((msg) {
            if (msg.id == event.messageId) {
              final updatedData = Map<String, dynamic>.from(msg.data ?? {});
              updatedData['plan_id'] = planId;
              return msg.copyWith(data: updatedData);
            }
            return msg;
          }).toList();

          emit(currentState.copyWith(messages: updatedMessages));
          event.onComplete?.call(planId);
        },
      );
    } catch (e) {
      event.onComplete?.call(null);
    }
  }

  Future<void> _onFeedbackSubmitted(
    AssistantFeedbackSubmitted event,
    Emitter<AssistantState> emit,
  ) async {
    if (state is! AssistantLoaded) return;
    final currentState = state as AssistantLoaded;

    final feedbackValue = event.isPositive ? 'positive' : 'negative';

    // Optimistically update the message's feedback state
    final updatedMessages = currentState.messages.map((msg) {
      if (msg.id == event.messageId) {
        return msg.copyWith(
          feedback: feedbackValue,
          feedbackReason: event.reason,
        );
      }
      return msg;
    }).toList();

    emit(currentState.copyWith(messages: updatedMessages));

    if (!_isServerMessageId(event.messageId)) {
      debugPrint(
        '[CHAT FEEDBACK] skip non-server message id=${event.messageId}',
      );
      return;
    }

    // Fire-and-forget API call
    repository.submitFeedback(
      messageId: event.messageId,
      feedback: feedbackValue,
      reason: event.reason,
    );
  }

  Future<void> _onSyncPendingActions(
    AssistantSyncPendingActions event,
    Emitter<AssistantState> emit,
  ) async {
    if (pendingActionDatasource == null) return;
    if (state is! AssistantLoaded) return;
    final currentState = state as AssistantLoaded;

    try {
      final pendingActions = await pendingActionDatasource!.fetchPending();
      if (pendingActions.isEmpty) return;

      final existingActionIds = <String>{};
      for (final msg in currentState.messages) {
        if (msg.intent == 'confirmation_required' && msg.data != null) {
          final actionId = msg.data!['action_id'] as String?;
          if (actionId != null) {
            existingActionIds.add(actionId);
          }
        }
      }

      final newMessages = <ChatMessage>[];
      for (final action in pendingActions) {
        final actionId = action['id'] as String?;
        if (actionId == null || existingActionIds.contains(actionId)) continue;

        newMessages.add(ChatMessage(
          id: 'sync-$actionId',
          sessionId: currentState.sessionId ?? '',
          role: MessageRole.assistant,
          content: '',
          intent: 'confirmation_required',
          data: {
            'action_id': actionId,
            'action_type': action['action_type'],
            'display': {
              'title': action['display_title'] ?? '',
              'details': (action['display_details'] as List?)
                      ?.map((d) => {
                            'label': d['label'] ?? '',
                            'value': d['value'] ?? '',
                          })
                      .toList() ??
                  [],
            },
          },
          createdAt: DateTime.now(),
        ));
      }

      if (newMessages.isNotEmpty) {
        var baseMessages = currentState.messages;
        final wasStreaming = currentState.isStreaming ||
            baseMessages
                .any((m) => m.role == MessageRole.assistant && m.isStreaming);

        if (wasStreaming) {
          baseMessages = baseMessages
              .where((m) => !(m.role == MessageRole.assistant &&
                  m.isStreaming &&
                  m.content.isEmpty))
              .toList();
        }

        emit(currentState.copyWith(
          messages: [...baseMessages, ...newMessages],
          isStreaming: wasStreaming ? false : currentState.isStreaming,
          clearActiveJobId: wasStreaming,
          progressStage: wasStreaming
              ? 'waiting_confirmation'
              : currentState.progressStage,
          progressMessage: wasStreaming
              ? '\u7b49\u5f85\u7528\u6237\u786e\u8ba4...'
              : currentState.progressMessage,
        ));
      }
    } catch (e, stackTrace) {
      debugPrint('PendingAction sync failed: $e\n$stackTrace');
    }
  }
}
