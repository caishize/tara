import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:equatable/equatable.dart';

import '../../data/datasources/memory_browser_remote_datasource.dart';
import '../../data/models/memory_item_model.dart';

// Events
abstract class MemoryBrowserEvent extends Equatable {
  const MemoryBrowserEvent();

  @override
  List<Object?> get props => [];
}

class LoadMemories extends MemoryBrowserEvent {
  const LoadMemories();
}

class LoadMoreMemories extends MemoryBrowserEvent {
  const LoadMoreMemories();
}

class SearchMemories extends MemoryBrowserEvent {
  final String query;

  const SearchMemories(this.query);

  @override
  List<Object?> get props => [query];
}

class FilterByType extends MemoryBrowserEvent {
  final String? type;

  const FilterByType(this.type);

  @override
  List<Object?> get props => [type];
}

class ArchiveMemory extends MemoryBrowserEvent {
  final String memoryId;

  const ArchiveMemory(this.memoryId);

  @override
  List<Object?> get props => [memoryId];
}

class DeleteMemory extends MemoryBrowserEvent {
  final String memoryId;

  const DeleteMemory(this.memoryId);

  @override
  List<Object?> get props => [memoryId];
}

class LoadInsights extends MemoryBrowserEvent {
  const LoadInsights();
}

class SubmitInsightFeedback extends MemoryBrowserEvent {
  final String insightId;
  final String feedbackType;

  const SubmitInsightFeedback({
    required this.insightId,
    required this.feedbackType,
  });

  @override
  List<Object?> get props => [insightId, feedbackType];
}

// States
abstract class MemoryBrowserState extends Equatable {
  const MemoryBrowserState();

  @override
  List<Object?> get props => [];
}

class MemoryBrowserInitial extends MemoryBrowserState {
  const MemoryBrowserInitial();
}

class MemoryBrowserLoading extends MemoryBrowserState {
  const MemoryBrowserLoading();
}

class MemoryBrowserLoaded extends MemoryBrowserState {
  final List<MemoryItem> memories;
  final List<InsightItem> insights;
  final String? activeFilter;
  final String? searchQuery;
  final bool hasMore;
  final bool isLoadingMore;

  const MemoryBrowserLoaded({
    required this.memories,
    required this.insights,
    this.activeFilter,
    this.searchQuery,
    this.hasMore = false,
    this.isLoadingMore = false,
  });

  @override
  List<Object?> get props => [
        memories,
        insights,
        activeFilter,
        searchQuery,
        hasMore,
        isLoadingMore,
      ];

  MemoryBrowserLoaded copyWith({
    List<MemoryItem>? memories,
    List<InsightItem>? insights,
    String? activeFilter,
    String? searchQuery,
    bool? hasMore,
    bool? isLoadingMore,
  }) {
    return MemoryBrowserLoaded(
      memories: memories ?? this.memories,
      insights: insights ?? this.insights,
      activeFilter: activeFilter,
      searchQuery: searchQuery,
      hasMore: hasMore ?? this.hasMore,
      isLoadingMore: isLoadingMore ?? this.isLoadingMore,
    );
  }
}

class MemoryBrowserError extends MemoryBrowserState {
  final String message;

  const MemoryBrowserError(this.message);

  @override
  List<Object?> get props => [message];
}

// BLoC
class MemoryBrowserBloc
    extends Bloc<MemoryBrowserEvent, MemoryBrowserState> {
  final MemoryBrowserRemoteDataSource dataSource;

  static const int _pageSize = 20;

  MemoryBrowserBloc({required this.dataSource})
      : super(const MemoryBrowserInitial()) {
    on<LoadMemories>(_onLoadMemories);
    on<LoadMoreMemories>(_onLoadMoreMemories);
    on<SearchMemories>(_onSearchMemories);
    on<FilterByType>(_onFilterByType);
    on<ArchiveMemory>(_onArchiveMemory);
    on<DeleteMemory>(_onDeleteMemory);
    on<LoadInsights>(_onLoadInsights);
    on<SubmitInsightFeedback>(_onSubmitInsightFeedback);
  }

  Future<void> _onLoadMemories(
    LoadMemories event,
    Emitter<MemoryBrowserState> emit,
  ) async {
    emit(const MemoryBrowserLoading());
    try {
      final response = await dataSource.fetchMemories(
        offset: 0,
        limit: _pageSize,
      );
      final insights = await dataSource.fetchInsights();
      emit(MemoryBrowserLoaded(
        memories: response.items,
        insights: insights,
        hasMore: response.hasMore,
      ));
    } catch (e) {
      emit(MemoryBrowserError('加载记忆失败: $e'));
    }
  }

  Future<void> _onLoadMoreMemories(
    LoadMoreMemories event,
    Emitter<MemoryBrowserState> emit,
  ) async {
    final currentState = state;
    if (currentState is! MemoryBrowserLoaded || !currentState.hasMore) return;
    if (currentState.isLoadingMore) return;

    emit(currentState.copyWith(isLoadingMore: true));

    try {
      final nextOffset = currentState.memories.length;
      final response = await dataSource.fetchMemories(
        type: currentState.activeFilter,
        offset: nextOffset,
        limit: _pageSize,
      );
      emit(currentState.copyWith(
        memories: [...currentState.memories, ...response.items],
        hasMore: response.hasMore,
        isLoadingMore: false,
      ));
    } catch (e) {
      emit(currentState.copyWith(isLoadingMore: false));
    }
  }

  Future<void> _onSearchMemories(
    SearchMemories event,
    Emitter<MemoryBrowserState> emit,
  ) async {
    emit(const MemoryBrowserLoading());
    try {
      final results = await dataSource.searchMemories(event.query);
      emit(MemoryBrowserLoaded(
        memories: results,
        insights: const [],
        searchQuery: event.query,
        hasMore: false,
      ));
    } catch (e) {
      emit(MemoryBrowserError('搜索失败: $e'));
    }
  }

  Future<void> _onFilterByType(
    FilterByType event,
    Emitter<MemoryBrowserState> emit,
  ) async {
    emit(const MemoryBrowserLoading());
    try {
      final response = await dataSource.fetchMemories(
        type: event.type,
        offset: 0,
        limit: _pageSize,
      );
      final insights = await dataSource.fetchInsights();
      emit(MemoryBrowserLoaded(
        memories: response.items,
        insights: insights,
        activeFilter: event.type,
        hasMore: response.hasMore,
      ));
    } catch (e) {
      emit(MemoryBrowserError('加载记忆失败: $e'));
    }
  }

  Future<void> _onArchiveMemory(
    ArchiveMemory event,
    Emitter<MemoryBrowserState> emit,
  ) async {
    final currentState = state;
    if (currentState is! MemoryBrowserLoaded) return;

    try {
      await dataSource.archiveMemory(event.memoryId);
      final updatedMemories = currentState.memories
          .where((m) => m.id != event.memoryId)
          .toList();
      emit(currentState.copyWith(memories: updatedMemories));
    } catch (e) {
      // Silently fail, memory stays in list
    }
  }

  Future<void> _onDeleteMemory(
    DeleteMemory event,
    Emitter<MemoryBrowserState> emit,
  ) async {
    final currentState = state;
    if (currentState is! MemoryBrowserLoaded) return;

    try {
      await dataSource.deleteMemory(event.memoryId);
      final updatedMemories = currentState.memories
          .where((m) => m.id != event.memoryId)
          .toList();
      emit(currentState.copyWith(memories: updatedMemories));
    } catch (e) {
      // Silently fail, memory stays in list
    }
  }

  Future<void> _onLoadInsights(
    LoadInsights event,
    Emitter<MemoryBrowserState> emit,
  ) async {
    final currentState = state;
    if (currentState is! MemoryBrowserLoaded) return;

    try {
      final insights = await dataSource.fetchInsights();
      emit(currentState.copyWith(insights: insights));
    } catch (e) {
      // Keep existing insights on error
    }
  }

  Future<void> _onSubmitInsightFeedback(
    SubmitInsightFeedback event,
    Emitter<MemoryBrowserState> emit,
  ) async {
    final currentState = state;
    if (currentState is! MemoryBrowserLoaded) return;

    try {
      await dataSource.submitInsightFeedback(
        event.insightId,
        event.feedbackType,
      );
      final updatedInsights = currentState.insights
          .where((i) => i.id != event.insightId)
          .toList();
      emit(currentState.copyWith(insights: updatedInsights));
    } catch (e) {
      // Keep insight in list on error
    }
  }
}
