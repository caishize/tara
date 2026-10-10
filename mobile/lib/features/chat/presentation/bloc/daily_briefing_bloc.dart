import 'dart:io';

import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:equatable/equatable.dart';

import '../../domain/entities/daily_briefing.dart';
import '../../domain/repositories/briefing_repository.dart';
import '../../data/models/memory_model.dart';

/// Error types for better user feedback
enum BriefingErrorType {
  network,     // No internet connection
  server,      // Server returned error (5xx)
  auth,        // Authentication failed
  notFound,    // Resource not found (404)
  unknown,     // Unknown error
}

/// Parse error type from exception
BriefingErrorType _parseErrorType(dynamic error) {
  final errorStr = error.toString().toLowerCase();

  if (error is SocketException || errorStr.contains('socketexception')) {
    return BriefingErrorType.network;
  }
  if (errorStr.contains('401') || errorStr.contains('unauthorized')) {
    return BriefingErrorType.auth;
  }
  if (errorStr.contains('404') || errorStr.contains('not found')) {
    return BriefingErrorType.notFound;
  }
  if (errorStr.contains('500') || errorStr.contains('502') ||
      errorStr.contains('503') || errorStr.contains('504')) {
    return BriefingErrorType.server;
  }
  if (errorStr.contains('timeout') || errorStr.contains('connection')) {
    return BriefingErrorType.network;
  }
  return BriefingErrorType.unknown;
}

/// Get user-friendly error message
String _getErrorMessage(BriefingErrorType type, String context) {
  switch (type) {
    case BriefingErrorType.network:
      return '网络连接失败，请检查网络后重试';
    case BriefingErrorType.server:
      return '服务器暂时不可用，请稍后重试';
    case BriefingErrorType.auth:
      return '登录已过期，请重新登录';
    case BriefingErrorType.notFound:
      return '$context未找到';
    case BriefingErrorType.unknown:
      return '$context失败，请稍后重试';
  }
}

// Events
abstract class DailyBriefingEvent extends Equatable {
  const DailyBriefingEvent();

  @override
  List<Object?> get props => [];
}

class LoadDailyBriefingRequested extends DailyBriefingEvent {
  final DateTime? targetDate;

  const LoadDailyBriefingRequested({this.targetDate});

  @override
  List<Object?> get props => [targetDate];
}

class RefreshDailyBriefingRequested extends DailyBriefingEvent {
  const RefreshDailyBriefingRequested();
}

class LoadInsightsRequested extends DailyBriefingEvent {
  const LoadInsightsRequested();
}

class GenerateInsightsRequested extends DailyBriefingEvent {
  const GenerateInsightsRequested();
}

class ExecuteInsightActionRequested extends DailyBriefingEvent {
  final String insightId;
  final String action;
  final Map<String, dynamic>? params;

  const ExecuteInsightActionRequested({
    required this.insightId,
    required this.action,
    this.params,
  });

  @override
  List<Object?> get props => [insightId, action, params];
}

class LoadMemoriesRequested extends DailyBriefingEvent {
  final String? memoryType;

  const LoadMemoriesRequested({this.memoryType});

  @override
  List<Object?> get props => [memoryType];
}

// States
abstract class DailyBriefingState extends Equatable {
  const DailyBriefingState();

  @override
  List<Object?> get props => [];
}

class DailyBriefingInitial extends DailyBriefingState {
  const DailyBriefingInitial();
}

class DailyBriefingLoading extends DailyBriefingState {
  const DailyBriefingLoading();
}

class DailyBriefingLoaded extends DailyBriefingState {
  final DailyBriefing briefing;
  final List<InsightModel> insights;
  final List<MemoryModel> recentMemories;
  final bool isLoadingInsights;
  final bool isLoadingMemories;
  final String? insightsError;   // Non-critical error for insights
  final String? memoriesError;   // Non-critical error for memories

  const DailyBriefingLoaded({
    required this.briefing,
    this.insights = const [],
    this.recentMemories = const [],
    this.isLoadingInsights = false,
    this.isLoadingMemories = false,
    this.insightsError,
    this.memoriesError,
  });

  DailyBriefingLoaded copyWith({
    DailyBriefing? briefing,
    List<InsightModel>? insights,
    List<MemoryModel>? recentMemories,
    bool? isLoadingInsights,
    bool? isLoadingMemories,
    String? insightsError,
    String? memoriesError,
    bool clearInsightsError = false,
    bool clearMemoriesError = false,
  }) {
    return DailyBriefingLoaded(
      briefing: briefing ?? this.briefing,
      insights: insights ?? this.insights,
      recentMemories: recentMemories ?? this.recentMemories,
      isLoadingInsights: isLoadingInsights ?? this.isLoadingInsights,
      isLoadingMemories: isLoadingMemories ?? this.isLoadingMemories,
      insightsError: clearInsightsError ? null : (insightsError ?? this.insightsError),
      memoriesError: clearMemoriesError ? null : (memoriesError ?? this.memoriesError),
    );
  }

  @override
  List<Object?> get props => [
        briefing,
        insights,
        recentMemories,
        isLoadingInsights,
        isLoadingMemories,
        insightsError,
        memoriesError,
      ];

  /// Whether there's a non-critical error to show
  bool get hasPartialError => insightsError != null || memoriesError != null;

  /// Get high-priority insights
  List<InsightModel> get urgentInsights =>
      insights.where((i) => i.isUrgent || i.isHighPriority).toList();

  /// Check if there are any insights to display
  bool get hasInsights => insights.isNotEmpty;

  /// Check if there are any urgent insights
  bool get hasUrgentInsights => urgentInsights.isNotEmpty;
}

class DailyBriefingError extends DailyBriefingState {
  final String message;
  final BriefingErrorType errorType;
  final bool canRetry;

  const DailyBriefingError({
    required this.message,
    this.errorType = BriefingErrorType.unknown,
    this.canRetry = true,
  });

  @override
  List<Object?> get props => [message, errorType, canRetry];

  /// Whether this error requires re-authentication
  bool get requiresAuth => errorType == BriefingErrorType.auth;

  /// Whether this is a network error
  bool get isNetworkError => errorType == BriefingErrorType.network;
}

// BLoC
class DailyBriefingBloc extends Bloc<DailyBriefingEvent, DailyBriefingState> {
  final SecretaryRepository _repository;

  DailyBriefingBloc(this._repository) : super(const DailyBriefingInitial()) {
    on<LoadDailyBriefingRequested>(_onLoadBriefing);
    on<RefreshDailyBriefingRequested>(_onRefreshBriefing);
    on<LoadInsightsRequested>(_onLoadInsights);
    on<GenerateInsightsRequested>(_onGenerateInsights);
    on<ExecuteInsightActionRequested>(_onExecuteInsightAction);
    on<LoadMemoriesRequested>(_onLoadMemories);
  }

  Future<void> _onLoadBriefing(
    LoadDailyBriefingRequested event,
    Emitter<DailyBriefingState> emit,
  ) async {
    emit(const DailyBriefingLoading());

    try {
      final briefing = await _repository.getDailyBriefing(
        targetDate: event.targetDate,
      );

      emit(DailyBriefingLoaded(briefing: briefing));

      // Also load insights in the background (check if bloc is still open)
      if (!isClosed) {
        add(const LoadInsightsRequested());
      }
    } catch (e) {
      final errorType = _parseErrorType(e);
      final message = _getErrorMessage(errorType, '加载每日简报');
      emit(DailyBriefingError(
        message: message,
        errorType: errorType,
        canRetry: errorType != BriefingErrorType.auth,
      ));
    }
  }

  Future<void> _onRefreshBriefing(
    RefreshDailyBriefingRequested event,
    Emitter<DailyBriefingState> emit,
  ) async {
    try {
      final briefing = await _repository.getDailyBriefing();

      if (state is DailyBriefingLoaded) {
        emit((state as DailyBriefingLoaded).copyWith(briefing: briefing));
      } else {
        emit(DailyBriefingLoaded(briefing: briefing));
      }

      // Also refresh insights (check if bloc is still open)
      if (!isClosed) {
        add(const LoadInsightsRequested());
      }
    } catch (e) {
      final errorType = _parseErrorType(e);
      final message = _getErrorMessage(errorType, '刷新简报');
      emit(DailyBriefingError(
        message: message,
        errorType: errorType,
        canRetry: errorType != BriefingErrorType.auth,
      ));
    }
  }

  Future<void> _onLoadInsights(
    LoadInsightsRequested event,
    Emitter<DailyBriefingState> emit,
  ) async {
    if (state is! DailyBriefingLoaded) return;

    final currentState = state as DailyBriefingLoaded;
    emit(currentState.copyWith(isLoadingInsights: true, clearInsightsError: true));

    try {
      final insights = await _repository.getInsights(
        status: 'active',
        limit: 10,
      );

      emit(currentState.copyWith(
        insights: insights,
        isLoadingInsights: false,
        clearInsightsError: true,
      ));
    } catch (e) {
      // Non-critical error - store it but don't fail the whole page
      final errorType = _parseErrorType(e);
      final message = _getErrorMessage(errorType, '加载智能提醒');
      emit(currentState.copyWith(
        isLoadingInsights: false,
        insightsError: message,
      ));
    }
  }

  Future<void> _onGenerateInsights(
    GenerateInsightsRequested event,
    Emitter<DailyBriefingState> emit,
  ) async {
    if (state is! DailyBriefingLoaded) return;

    final currentState = state as DailyBriefingLoaded;
    emit(currentState.copyWith(isLoadingInsights: true, clearInsightsError: true));

    try {
      final insights = await _repository.generateInsights();

      emit(currentState.copyWith(
        insights: insights,
        isLoadingInsights: false,
        clearInsightsError: true,
      ));
    } catch (e) {
      final errorType = _parseErrorType(e);
      final message = _getErrorMessage(errorType, '生成智能提醒');
      emit(currentState.copyWith(
        isLoadingInsights: false,
        insightsError: message,
      ));
    }
  }

  Future<void> _onExecuteInsightAction(
    ExecuteInsightActionRequested event,
    Emitter<DailyBriefingState> emit,
  ) async {
    if (state is! DailyBriefingLoaded) return;

    final currentState = state as DailyBriefingLoaded;

    try {
      await _repository.executeInsightAction(
        event.insightId,
        event.action,
        params: event.params,
      );

      // Remove the insight from the list if it was handled
      final updatedInsights = currentState.insights
          .where((i) => i.id != event.insightId)
          .toList();

      emit(currentState.copyWith(insights: updatedInsights, clearInsightsError: true));
    } catch (e) {
      // Show error but don't fail - user can retry
      final errorType = _parseErrorType(e);
      final message = _getErrorMessage(errorType, '处理提醒');
      emit(currentState.copyWith(insightsError: message));
    }
  }

  Future<void> _onLoadMemories(
    LoadMemoriesRequested event,
    Emitter<DailyBriefingState> emit,
  ) async {
    if (state is! DailyBriefingLoaded) return;

    final currentState = state as DailyBriefingLoaded;
    emit(currentState.copyWith(isLoadingMemories: true, clearMemoriesError: true));

    try {
      final response = await _repository.getMemories(
        memoryType: event.memoryType,
        status: 'active',
        limit: 10,
      );

      emit(currentState.copyWith(
        recentMemories: response.memories,
        isLoadingMemories: false,
        clearMemoriesError: true,
      ));
    } catch (e) {
      final errorType = _parseErrorType(e);
      final message = _getErrorMessage(errorType, '加载记忆');
      emit(currentState.copyWith(
        isLoadingMemories: false,
        memoriesError: message,
      ));
    }
  }
}
