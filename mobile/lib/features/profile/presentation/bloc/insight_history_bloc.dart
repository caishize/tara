import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:equatable/equatable.dart';

import '../../data/datasources/memory_browser_remote_datasource.dart';
import '../../data/models/memory_item_model.dart';

// Events
abstract class InsightHistoryEvent extends Equatable {
  const InsightHistoryEvent();

  @override
  List<Object?> get props => [];
}

class LoadInsightHistory extends InsightHistoryEvent {
  const LoadInsightHistory();
}

class FilterInsightsByType extends InsightHistoryEvent {
  final String? type;

  const FilterInsightsByType(this.type);

  @override
  List<Object?> get props => [type];
}

class SearchInsights extends InsightHistoryEvent {
  final String query;

  const SearchInsights(this.query);

  @override
  List<Object?> get props => [query];
}

class SubmitInsightHistoryFeedback extends InsightHistoryEvent {
  final String insightId;
  final String feedbackType;

  const SubmitInsightHistoryFeedback({
    required this.insightId,
    required this.feedbackType,
  });

  @override
  List<Object?> get props => [insightId, feedbackType];
}

// States
abstract class InsightHistoryState extends Equatable {
  const InsightHistoryState();

  @override
  List<Object?> get props => [];
}

class InsightHistoryInitial extends InsightHistoryState {
  const InsightHistoryInitial();
}

class InsightHistoryLoading extends InsightHistoryState {
  const InsightHistoryLoading();
}

class InsightHistoryLoaded extends InsightHistoryState {
  final List<InsightItem> insights;
  final String? activeFilter;
  final String? searchQuery;

  const InsightHistoryLoaded({
    required this.insights,
    this.activeFilter,
    this.searchQuery,
  });

  @override
  List<Object?> get props => [insights, activeFilter, searchQuery];

  InsightHistoryLoaded copyWith({
    List<InsightItem>? insights,
    String? activeFilter,
    String? searchQuery,
  }) {
    return InsightHistoryLoaded(
      insights: insights ?? this.insights,
      activeFilter: activeFilter,
      searchQuery: searchQuery,
    );
  }
}

class InsightHistoryError extends InsightHistoryState {
  final String message;

  const InsightHistoryError(this.message);

  @override
  List<Object?> get props => [message];
}

// BLoC
class InsightHistoryBloc
    extends Bloc<InsightHistoryEvent, InsightHistoryState> {
  final MemoryBrowserRemoteDataSource dataSource;

  InsightHistoryBloc({required this.dataSource})
      : super(const InsightHistoryInitial()) {
    on<LoadInsightHistory>(_onLoad);
    on<FilterInsightsByType>(_onFilter);
    on<SearchInsights>(_onSearch);
    on<SubmitInsightHistoryFeedback>(_onFeedback);
  }

  Future<void> _onLoad(
    LoadInsightHistory event,
    Emitter<InsightHistoryState> emit,
  ) async {
    emit(const InsightHistoryLoading());
    try {
      final insights = await dataSource.fetchAllInsights(limit: 50);
      emit(InsightHistoryLoaded(insights: insights));
    } catch (e) {
      emit(InsightHistoryError('加载洞察失败: $e'));
    }
  }

  Future<void> _onFilter(
    FilterInsightsByType event,
    Emitter<InsightHistoryState> emit,
  ) async {
    emit(const InsightHistoryLoading());
    try {
      final insights = await dataSource.fetchAllInsights(
        type: event.type,
        limit: 50,
      );
      emit(InsightHistoryLoaded(
        insights: insights,
        activeFilter: event.type,
      ));
    } catch (e) {
      emit(InsightHistoryError('加载洞察失败: $e'));
    }
  }

  Future<void> _onSearch(
    SearchInsights event,
    Emitter<InsightHistoryState> emit,
  ) async {
    final currentState = state;
    if (currentState is! InsightHistoryLoaded) return;

    // Client-side filter by search query
    final query = event.query.toLowerCase();
    final allInsights = await dataSource.fetchAllInsights(
      type: currentState.activeFilter,
      limit: 50,
    );
    final filtered = allInsights
        .where((i) =>
            i.content.toLowerCase().contains(query) ||
            i.title.toLowerCase().contains(query))
        .toList();
    emit(currentState.copyWith(
      insights: filtered,
      searchQuery: event.query,
    ));
  }

  Future<void> _onFeedback(
    SubmitInsightHistoryFeedback event,
    Emitter<InsightHistoryState> emit,
  ) async {
    final currentState = state;
    if (currentState is! InsightHistoryLoaded) return;

    try {
      await dataSource.submitInsightFeedback(
        event.insightId,
        event.feedbackType,
      );
      // Update local state: mark feedback as submitted
      final updated = currentState.insights.map((i) {
        if (i.id == event.insightId) {
          return InsightItem(
            id: i.id,
            type: i.type,
            title: i.title,
            content: i.content,
            priority: i.priority,
            urgency: i.urgency,
            status: event.feedbackType == 'useful' ? 'acted' : 'dismissed',
            relatedMemoryIds: i.relatedMemoryIds,
            actionOptions: i.actionOptions,
            createdAt: i.createdAt,
          );
        }
        return i;
      }).toList();
      emit(currentState.copyWith(insights: updated));
    } catch (e) {
      // Keep current state on error
    }
  }
}
