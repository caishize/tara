import 'package:flutter_bloc/flutter_bloc.dart';
import '../../domain/entities/memory_lane.dart';
import '../../domain/repositories/curated_timeline_repository.dart';
import '../../domain/repositories/insight_feed_repository.dart';
import 'memory_lane_event.dart';
import 'memory_lane_state.dart';

/// Memory lane BLoC — past stories, on-this-day, yearly summaries
class MemoryLaneBloc extends Bloc<MemoryLaneEvent, MemoryLaneState> {
  final CuratedTimelineRepository _repository;
  final InsightFeedRepository? _insightFeedRepository;

  MemoryLaneBloc({
    required CuratedTimelineRepository repository,
    InsightFeedRepository? insightFeedRepository,
  })  : _repository = repository,
        _insightFeedRepository = insightFeedRepository,
        super(const MemoryLaneInitial()) {
    on<LoadMemoryLane>(_onLoadMemoryLane);
    on<LoadOnThisDay>(_onLoadOnThisDay);
    on<DismissOnThisDay>(_onDismissOnThisDay);
    on<LoadYearDetail>(_onLoadYearDetail);
    on<LoadMemoryHighlights>(_onLoadMemoryHighlights);
  }

  /// Load memory lane (past stories + yearly summaries)
  Future<void> _onLoadMemoryLane(
    LoadMemoryLane event,
    Emitter<MemoryLaneState> emit,
  ) async {
    final currentState = state;
    if (currentState is MemoryLaneLoaded) {
      emit(currentState.copyWith(isRefreshing: true));
    } else {
      emit(const MemoryLaneLoading());
    }

    final result = await _repository.getMemoryLane();

    result.fold(
      (failure) => emit(MemoryLaneError(message: failure.message)),
      (memoryLane) {
        final preserved = currentState is MemoryLaneLoaded
            ? currentState.dismissedOnThisDayIds
            : const <String>{};
        final preservedOnThisDay = currentState is MemoryLaneLoaded
            ? currentState.onThisDayItems
            : const <OnThisDayItem>[];
        emit(MemoryLaneLoaded(
          onThisDayItems:
              preservedOnThisDay.isNotEmpty ? preservedOnThisDay : const [],
          recentStories: memoryLane.recentStories,
          yearlySummaries: memoryLane.years,
          dismissedOnThisDayIds: preserved,
        ));
      },
    );
  }

  /// Load on-this-day items
  Future<void> _onLoadOnThisDay(
    LoadOnThisDay event,
    Emitter<MemoryLaneState> emit,
  ) async {
    final result = await _repository.getOnThisDay();

    result.fold(
      (failure) {
        // Silently ignore — on-this-day is optional enhancement
      },
      (response) {
        final currentState = state;
        if (currentState is MemoryLaneLoaded) {
          emit(currentState.copyWith(onThisDayItems: response.items));
        }
      },
    );
  }

  /// Dismiss an on-this-day card
  void _onDismissOnThisDay(
    DismissOnThisDay event,
    Emitter<MemoryLaneState> emit,
  ) {
    final currentState = state;
    if (currentState is MemoryLaneLoaded) {
      emit(currentState.copyWith(
        dismissedOnThisDayIds: {
          ...currentState.dismissedOnThisDayIds,
          event.eventId,
        },
      ));
    }
  }

  /// PLAN-011: Load AI memory reflection highlights from the insight feed.
  ///
  /// Fetches insights filtered to memory_reflection type and stores them
  /// in state for the AiMemoryHighlights widget to render.
  Future<void> _onLoadMemoryHighlights(
    LoadMemoryHighlights event,
    Emitter<MemoryLaneState> emit,
  ) async {
    final repo = _insightFeedRepository;
    if (repo == null) return;

    final result = await repo.getInsightFeed(limit: 5);

    result.fold(
      (failure) {
        // Silently ignore — highlights are an optional enhancement
      },
      (response) {
        // Filter to memory_reflection insights only
        final highlights = response.insights
            .where((i) => i.insightType == 'memory_reflection')
            .toList();

        // Also check grouped insights
        final groupedHighlights = response.groups
            .expand((g) => g.insights)
            .where((i) => i.insightType == 'memory_reflection')
            .toList();

        final allHighlights = [...highlights, ...groupedHighlights];

        final currentState = state;
        if (currentState is MemoryLaneLoaded) {
          emit(currentState.copyWith(memoryHighlights: allHighlights));
        }
      },
    );
  }

  /// Load detail stories for a specific year
  Future<void> _onLoadYearDetail(
    LoadYearDetail event,
    Emitter<MemoryLaneState> emit,
  ) async {
    final currentState = state;
    if (currentState is! MemoryLaneLoaded) return;

    // Toggle expand
    final newExpanded = Set<int>.from(currentState.expandedYears);
    if (newExpanded.contains(event.year)) {
      newExpanded.remove(event.year);
      emit(currentState.copyWith(expandedYears: newExpanded));
      return;
    }

    newExpanded.add(event.year);
    emit(currentState.copyWith(expandedYears: newExpanded));

    // Fetch year-specific data if stories are empty for this year
    final yearSummary = currentState.yearlySummaries
        .where((y) => y.year == event.year)
        .firstOrNull;

    if (yearSummary != null && yearSummary.stories.isNotEmpty) {
      return; // Already have data
    }

    final result = await _repository.getMemoryLane(year: event.year);

    result.fold(
      (failure) {
        // Keep expanded but no extra data
      },
      (memoryLane) {
        final updatedState = state;
        if (updatedState is! MemoryLaneLoaded) return;

        final updatedYears = updatedState.yearlySummaries.map((y) {
          if (y.year != event.year) return y;
          final yearData = memoryLane.years
              .where((yd) => yd.year == event.year)
              .firstOrNull;
          if (yearData == null) return y;
          return yearData;
        }).toList();

        emit(updatedState.copyWith(yearlySummaries: updatedYears));
      },
    );
  }
}
