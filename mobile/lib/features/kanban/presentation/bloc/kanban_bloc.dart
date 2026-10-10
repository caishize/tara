import 'package:flutter_bloc/flutter_bloc.dart';
import '../../data/models/kanban_models.dart';
import '../../domain/repositories/curated_timeline_repository.dart';
import 'kanban_event.dart';
import 'kanban_state.dart';

/// Kanban semantic view BLoC.
///
/// Handles the legacy kanban board (buckets), search, and preparation items.
/// Insight-centric feed handling has been migrated to [InsightFeedBloc].
class KanbanBloc extends Bloc<KanbanEvent, KanbanState> {
  final CuratedTimelineRepository _repository;

  KanbanBloc({required CuratedTimelineRepository repository})
      : _repository = repository,
        super(const KanbanInitial()) {
    on<LoadKanbanView>(_onLoadKanbanView);
    on<TogglePreparationItem>(_onTogglePreparationItem);
    on<SearchEvents>(_onSearchEvents);
    on<ClearSearch>(_onClearSearch);
  }

  /// Load kanban semantic view
  Future<void> _onLoadKanbanView(
    LoadKanbanView event,
    Emitter<KanbanState> emit,
  ) async {
    final currentState = state;
    if (currentState is KanbanLoaded) {
      emit(currentState.copyWith(isRefreshing: true));
    } else {
      emit(const KanbanLoading());
    }

    final result = await _repository.getKanban();

    result.fold(
      (failure) => emit(KanbanError(message: failure.message)),
      (kanban) => emit(KanbanLoaded(kanban: kanban)),
    );
  }

  /// Toggle a preparation item checkbox and update local state optimistically
  Future<void> _onTogglePreparationItem(
    TogglePreparationItem event,
    Emitter<KanbanState> emit,
  ) async {
    final currentState = state;
    if (currentState is! KanbanLoaded) return;

    // Optimistic update: toggle the item locally
    final updatedKanban = _togglePrepItemLocally(
      currentState.kanban,
      event.eventId,
      event.itemIndex,
      event.done,
    );
    emit(currentState.copyWith(kanban: updatedKanban));

    // Send to backend
    final result = await _repository.togglePreparationItem(
      eventId: event.eventId,
      itemIndex: event.itemIndex,
      itemKey: event.itemKey,
      done: event.done,
    );

    result.fold(
      (failure) {
        // Revert on failure
        emit(currentState);
      },
      (_) {
        // Success — local state already reflects the change
      },
    );
  }

  /// Search events by query
  Future<void> _onSearchEvents(
    SearchEvents event,
    Emitter<KanbanState> emit,
  ) async {
    if (event.query.trim().isEmpty) {
      // Empty query — go back to kanban
      add(const LoadKanbanView());
      return;
    }

    emit(KanbanSearchResults(query: event.query, isSearching: true));

    final result = await _repository.searchEvents(
      query: event.query,
      eventTypes: event.eventTypes,
    );

    result.fold(
      (failure) => emit(KanbanError(message: failure.message)),
      (response) => emit(KanbanSearchResults(
        query: event.query,
        results: response.results,
        total: response.total,
      )),
    );
  }

  /// Clear search and reload kanban
  void _onClearSearch(
    ClearSearch event,
    Emitter<KanbanState> emit,
  ) {
    add(const LoadKanbanView());
  }

  /// Toggle a single prep item in-memory across all kanban buckets
  KanbanResponseModel _togglePrepItemLocally(
    KanbanResponseModel kanban,
    String eventId,
    int itemIndex,
    bool done,
  ) {
    List<KanbanEventModel> updateBucket(List<KanbanEventModel> bucket) {
      return bucket.map((ev) {
        if (ev.id != eventId) return ev;
        if (itemIndex < 0 || itemIndex >= ev.preparationItems.length) return ev;
        final updatedItems = [
          for (int i = 0; i < ev.preparationItems.length; i++)
            i == itemIndex
                ? ev.preparationItems[i].copyWith(done: done)
                : ev.preparationItems[i],
        ];
        return ev.copyWith(preparationItems: updatedItems);
      }).toList();
    }

    return kanban.copyWith(
      thisWeek: updateBucket(kanban.thisWeek),
      needsPreparation: updateBucket(kanban.needsPreparation),
      monthly: updateBucket(kanban.monthly),
      later: updateBucket(kanban.later),
    );
  }
}
