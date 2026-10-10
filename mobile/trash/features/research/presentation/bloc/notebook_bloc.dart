import 'dart:async';
import 'package:equatable/equatable.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../domain/entities/notebook.dart';
import '../../domain/repositories/notebook_repository.dart';
import '../../data/datasources/notebook_remote_datasource.dart';

// ============ Events ============

abstract class NotebookEvent extends Equatable {
  const NotebookEvent();

  @override
  List<Object?> get props => [];
}

class LoadNotebooksEvent extends NotebookEvent {
  const LoadNotebooksEvent();
}

class RefreshNotebooksEvent extends NotebookEvent {
  const RefreshNotebooksEvent();
}

class CreateNotebookEvent extends NotebookEvent {
  final String name;
  final String? description;
  final String icon;
  final String color;

  const CreateNotebookEvent({
    required this.name,
    this.description,
    this.icon = '📚',
    this.color = '#6366F1',
  });

  @override
  List<Object?> get props => [name, description, icon, color];
}

class LoadNotebookDetailEvent extends NotebookEvent {
  final String notebookId;

  const LoadNotebookDetailEvent({required this.notebookId});

  @override
  List<Object?> get props => [notebookId];
}

class DeleteNotebookEvent extends NotebookEvent {
  final String notebookId;

  const DeleteNotebookEvent({required this.notebookId});

  @override
  List<Object?> get props => [notebookId];
}

class AddSourceEvent extends NotebookEvent {
  final String notebookId;
  final String type;
  final String content;
  final String? title;

  const AddSourceEvent({
    required this.notebookId,
    required this.type,
    required this.content,
    this.title,
  });

  @override
  List<Object?> get props => [notebookId, type, content, title];
}

class DeleteSourceEvent extends NotebookEvent {
  final String notebookId;
  final String sourceId;

  const DeleteSourceEvent({
    required this.notebookId,
    required this.sourceId,
  });

  @override
  List<Object?> get props => [notebookId, sourceId];
}

class SendChatMessageEvent extends NotebookEvent {
  final String notebookId;
  final String question;

  const SendChatMessageEvent({
    required this.notebookId,
    required this.question,
  });

  @override
  List<Object?> get props => [notebookId, question];
}

class GenerateSummaryEvent extends NotebookEvent {
  final String notebookId;
  final String format;

  const GenerateSummaryEvent({
    required this.notebookId,
    required this.format,
  });

  @override
  List<Object?> get props => [notebookId, format];
}

class ClearChatHistoryEvent extends NotebookEvent {
  final String notebookId;

  const ClearChatHistoryEvent({required this.notebookId});

  @override
  List<Object?> get props => [notebookId];
}

/// Event to retry the last failed operation
class RetryLastOperationEvent extends NotebookEvent {
  final NotebookEvent? lastEvent;

  const RetryLastOperationEvent({this.lastEvent});

  @override
  List<Object?> get props => [lastEvent];
}

// ============ States ============

abstract class NotebookState extends Equatable {
  const NotebookState();

  @override
  List<Object?> get props => [];
}

class NotebookInitial extends NotebookState {
  const NotebookInitial();
}

class NotebookLoading extends NotebookState {
  const NotebookLoading();
}

class NotebooksLoaded extends NotebookState {
  final List<Notebook> notebooks;

  const NotebooksLoaded({required this.notebooks});

  @override
  List<Object?> get props => [notebooks];
}

class NotebookDetailLoaded extends NotebookState {
  final Notebook notebook;
  // Chat Q&A state
  final bool isChatting;
  final String? chatResponse;
  final String? chatError;
  final String? chatThinkingMessage;
  final List<ChatSource>? chatSources;
  // Summary state (separate from chat)
  final bool isSummarizing;
  final String? summaryResponse;
  final String? summaryError;
  final String? summaryThinkingMessage;
  final List<ChatSource>? summarySources;
  // Source loading state
  final bool isAddingSource;

  const NotebookDetailLoaded({
    required this.notebook,
    this.isChatting = false,
    this.chatResponse,
    this.chatError,
    this.chatThinkingMessage,
    this.chatSources,
    this.isSummarizing = false,
    this.summaryResponse,
    this.summaryError,
    this.summaryThinkingMessage,
    this.summarySources,
    this.isAddingSource = false,
  });

  NotebookDetailLoaded copyWith({
    Notebook? notebook,
    bool? isChatting,
    String? chatResponse,
    String? chatError,
    String? chatThinkingMessage,
    List<ChatSource>? chatSources,
    bool? isSummarizing,
    String? summaryResponse,
    String? summaryError,
    String? summaryThinkingMessage,
    List<ChatSource>? summarySources,
    bool? isAddingSource,
  }) {
    return NotebookDetailLoaded(
      notebook: notebook ?? this.notebook,
      isChatting: isChatting ?? this.isChatting,
      chatResponse: chatResponse ?? this.chatResponse,
      chatError: chatError ?? this.chatError,
      chatThinkingMessage: chatThinkingMessage ?? this.chatThinkingMessage,
      chatSources: chatSources ?? this.chatSources,
      isSummarizing: isSummarizing ?? this.isSummarizing,
      summaryResponse: summaryResponse ?? this.summaryResponse,
      summaryError: summaryError ?? this.summaryError,
      summaryThinkingMessage: summaryThinkingMessage ?? this.summaryThinkingMessage,
      summarySources: summarySources ?? this.summarySources,
      isAddingSource: isAddingSource ?? this.isAddingSource,
    );
  }

  @override
  List<Object?> get props => [
    notebook, isChatting, chatResponse, chatError, chatThinkingMessage, chatSources,
    isSummarizing, summaryResponse, summaryError, summaryThinkingMessage, summarySources,
    isAddingSource,
  ];
}

enum NotebookErrorType {
  network('网络连接失败'),
  server('服务器错误'),
  notFound('资源不存在'),
  validation('输入验证失败'),
  timeout('请求超时'),
  unknown('未知错误');

  final String displayName;
  const NotebookErrorType(this.displayName);

  /// Parse error type from exception
  static NotebookErrorType fromException(dynamic e) {
    final errorStr = e.toString().toLowerCase();
    if (errorStr.contains('socket') || errorStr.contains('connection') || errorStr.contains('network')) {
      return NotebookErrorType.network;
    } else if (errorStr.contains('500') || errorStr.contains('502') || errorStr.contains('503')) {
      return NotebookErrorType.server;
    } else if (errorStr.contains('404') || errorStr.contains('not found')) {
      return NotebookErrorType.notFound;
    } else if (errorStr.contains('400') || errorStr.contains('validation')) {
      return NotebookErrorType.validation;
    } else if (errorStr.contains('timeout')) {
      return NotebookErrorType.timeout;
    }
    return NotebookErrorType.unknown;
  }
}

class NotebookError extends NotebookState {
  final String message;
  final NotebookErrorType errorType;
  final NotebookEvent? failedEvent;
  final bool canRetry;

  const NotebookError({
    required this.message,
    this.errorType = NotebookErrorType.unknown,
    this.failedEvent,
    this.canRetry = true,
  });

  /// Create a user-friendly error message
  String get userMessage {
    switch (errorType) {
      case NotebookErrorType.network:
        return '网络连接失败，请检查您的网络连接';
      case NotebookErrorType.server:
        return '服务器暂时不可用，请稍后重试';
      case NotebookErrorType.notFound:
        return '请求的资源不存在';
      case NotebookErrorType.validation:
        return '输入内容有误，请检查后重试';
      case NotebookErrorType.timeout:
        return '请求超时，请稍后重试';
      case NotebookErrorType.unknown:
        return message.length > 100 ? '操作失败，请重试' : message;
    }
  }

  @override
  List<Object?> get props => [message, errorType, failedEvent, canRetry];
}

class NotebookCreated extends NotebookState {
  final Notebook notebook;

  const NotebookCreated({required this.notebook});

  @override
  List<Object?> get props => [notebook];
}

class SourceAdded extends NotebookState {
  final NotebookSource source;

  const SourceAdded({required this.source});

  @override
  List<Object?> get props => [source];
}

// ============ BLoC ============

class NotebookBloc extends Bloc<NotebookEvent, NotebookState> {
  final NotebookRepository repository;
  StreamSubscription<ChatStreamEvent>? _chatSubscription;
  NotebookEvent? _lastFailedEvent;

  NotebookBloc({required this.repository}) : super(const NotebookInitial()) {
    on<LoadNotebooksEvent>(_onLoadNotebooks);
    on<RefreshNotebooksEvent>(_onRefreshNotebooks);
    on<CreateNotebookEvent>(_onCreateNotebook);
    on<LoadNotebookDetailEvent>(_onLoadNotebookDetail);
    on<DeleteNotebookEvent>(_onDeleteNotebook);
    on<AddSourceEvent>(_onAddSource);
    on<DeleteSourceEvent>(_onDeleteSource);
    on<SendChatMessageEvent>(_onSendChatMessage);
    on<GenerateSummaryEvent>(_onGenerateSummary);
    on<ClearChatHistoryEvent>(_onClearChatHistory);
    on<RetryLastOperationEvent>(_onRetryLastOperation);
  }

  /// Create an error state with proper error type detection
  NotebookError _createError(dynamic e, NotebookEvent event, {bool canRetry = true}) {
    _lastFailedEvent = canRetry ? event : null;
    return NotebookError(
      message: e.toString(),
      errorType: NotebookErrorType.fromException(e),
      failedEvent: canRetry ? event : null,
      canRetry: canRetry,
    );
  }

  Future<void> _onRetryLastOperation(
    RetryLastOperationEvent event,
    Emitter<NotebookState> emit,
  ) async {
    final eventToRetry = event.lastEvent ?? _lastFailedEvent;
    if (eventToRetry == null) return;

    // Re-dispatch the failed event
    add(eventToRetry);
  }

  Future<void> _onLoadNotebooks(
    LoadNotebooksEvent event,
    Emitter<NotebookState> emit,
  ) async {
    emit(const NotebookLoading());
    try {
      final notebooks = await repository.listNotebooks();
      _lastFailedEvent = null; // Clear on success
      emit(NotebooksLoaded(notebooks: notebooks));
    } catch (e) {
      emit(_createError(e, event));
    }
  }

  Future<void> _onRefreshNotebooks(
    RefreshNotebooksEvent event,
    Emitter<NotebookState> emit,
  ) async {
    try {
      final notebooks = await repository.listNotebooks();
      _lastFailedEvent = null;
      emit(NotebooksLoaded(notebooks: notebooks));
    } catch (e) {
      emit(_createError(e, event));
    }
  }

  Future<void> _onCreateNotebook(
    CreateNotebookEvent event,
    Emitter<NotebookState> emit,
  ) async {
    try {
      final notebook = await repository.createNotebook(
        name: event.name,
        description: event.description,
        icon: event.icon,
        color: event.color,
      );
      _lastFailedEvent = null;
      emit(NotebookCreated(notebook: notebook));

      // Reload notebooks list
      final notebooks = await repository.listNotebooks();
      emit(NotebooksLoaded(notebooks: notebooks));
    } catch (e) {
      emit(_createError(e, event));
    }
  }

  Future<void> _onLoadNotebookDetail(
    LoadNotebookDetailEvent event,
    Emitter<NotebookState> emit,
  ) async {
    emit(const NotebookLoading());
    try {
      final notebook = await repository.getNotebook(event.notebookId);
      _lastFailedEvent = null;
      emit(NotebookDetailLoaded(notebook: notebook));
    } catch (e) {
      emit(_createError(e, event));
    }
  }

  Future<void> _onDeleteNotebook(
    DeleteNotebookEvent event,
    Emitter<NotebookState> emit,
  ) async {
    try {
      await repository.deleteNotebook(event.notebookId);
      _lastFailedEvent = null;
      // Reload notebooks list
      final notebooks = await repository.listNotebooks();
      emit(NotebooksLoaded(notebooks: notebooks));
    } catch (e) {
      emit(_createError(e, event));
    }
  }

  Future<void> _onAddSource(
    AddSourceEvent event,
    Emitter<NotebookState> emit,
  ) async {
    final currentState = state;

    // Show loading state
    if (currentState is NotebookDetailLoaded) {
      emit(currentState.copyWith(isAddingSource: true));
    }

    try {
      final source = await repository.addSource(
        notebookId: event.notebookId,
        type: event.type,
        content: event.content,
        title: event.title,
      );
      _lastFailedEvent = null;
      emit(SourceAdded(source: source));

      // Reload notebook detail
      final notebook = await repository.getNotebook(event.notebookId);
      emit(NotebookDetailLoaded(notebook: notebook));
    } catch (e) {
      // Reset loading state on error
      if (currentState is NotebookDetailLoaded) {
        emit(currentState.copyWith(isAddingSource: false));
      }
      emit(_createError(e, event));
    }
  }

  Future<void> _onDeleteSource(
    DeleteSourceEvent event,
    Emitter<NotebookState> emit,
  ) async {
    try {
      await repository.deleteSource(
        notebookId: event.notebookId,
        sourceId: event.sourceId,
      );
      _lastFailedEvent = null;

      // Reload notebook detail
      final notebook = await repository.getNotebook(event.notebookId);
      emit(NotebookDetailLoaded(notebook: notebook));
    } catch (e) {
      emit(_createError(e, event));
    }
  }

  Future<void> _onSendChatMessage(
    SendChatMessageEvent event,
    Emitter<NotebookState> emit,
  ) async {
    final currentState = state;
    if (currentState is! NotebookDetailLoaded) return;

    // Check if notebook has content
    if (currentState.notebook.totalSources == 0) {
      emit(currentState.copyWith(
        chatError: '请先添加一些内容到知识库',
      ));
      return;
    }

    // Cancel any existing subscription
    await _chatSubscription?.cancel();

    emit(currentState.copyWith(
      isChatting: true,
      chatResponse: '',
      chatError: null,
      chatThinkingMessage: null,
      chatSources: null,
    ));

    String fullResponse = '';

    await emit.forEach<ChatStreamEvent>(
      repository.chatStream(
        notebookId: event.notebookId,
        question: event.question,
      ),
      onData: (chatEvent) {
        switch (chatEvent.type) {
          case ChatEventType.thinking:
            return currentState.copyWith(
              isChatting: true,
              chatThinkingMessage: chatEvent.message,
              chatResponse: fullResponse,
            );
          case ChatEventType.content:
            fullResponse += chatEvent.content ?? '';
            return currentState.copyWith(
              isChatting: true,
              chatResponse: fullResponse,
              chatThinkingMessage: null,
            );
          case ChatEventType.sources:
            return currentState.copyWith(
              isChatting: true,
              chatResponse: fullResponse,
              chatSources: chatEvent.sources,
            );
          case ChatEventType.done:
            return currentState.copyWith(
              isChatting: false,
              chatResponse: fullResponse,
            );
          case ChatEventType.error:
            return currentState.copyWith(
              isChatting: false,
              chatError: chatEvent.error,
            );
        }
      },
    );
  }

  Future<void> _onGenerateSummary(
    GenerateSummaryEvent event,
    Emitter<NotebookState> emit,
  ) async {
    final currentState = state;
    if (currentState is! NotebookDetailLoaded) return;

    // Check if notebook has content
    if (currentState.notebook.totalSources == 0) {
      emit(currentState.copyWith(
        summaryError: '请先添加一些内容到知识库',
      ));
      return;
    }

    emit(currentState.copyWith(
      isSummarizing: true,
      summaryResponse: '',
      summaryError: null,
      summaryThinkingMessage: null,
      summarySources: null,
    ));

    String fullResponse = '';

    await emit.forEach<ChatStreamEvent>(
      repository.summarizeStream(
        notebookId: event.notebookId,
        format: event.format,
      ),
      onData: (chatEvent) {
        switch (chatEvent.type) {
          case ChatEventType.thinking:
            return currentState.copyWith(
              isSummarizing: true,
              summaryThinkingMessage: chatEvent.message,
              summaryResponse: fullResponse,
            );
          case ChatEventType.content:
            fullResponse += chatEvent.content ?? '';
            return currentState.copyWith(
              isSummarizing: true,
              summaryResponse: fullResponse,
              summaryThinkingMessage: null,
            );
          case ChatEventType.sources:
            return currentState.copyWith(
              isSummarizing: true,
              summaryResponse: fullResponse,
              summarySources: chatEvent.sources,
            );
          case ChatEventType.done:
            return currentState.copyWith(
              isSummarizing: false,
              summaryResponse: fullResponse,
            );
          case ChatEventType.error:
            return currentState.copyWith(
              isSummarizing: false,
              summaryError: chatEvent.error,
            );
        }
      },
    );
  }

  Future<void> _onClearChatHistory(
    ClearChatHistoryEvent event,
    Emitter<NotebookState> emit,
  ) async {
    try {
      await repository.clearChatHistory(event.notebookId);

      // Reload notebook detail
      final notebook = await repository.getNotebook(event.notebookId);
      emit(NotebookDetailLoaded(notebook: notebook));
    } catch (e) {
      emit(NotebookError(message: e.toString()));
    }
  }

  @override
  Future<void> close() {
    _chatSubscription?.cancel();
    return super.close();
  }
}
