import 'package:flutter_bloc/flutter_bloc.dart';
import '../../data/models/future_view_models.dart';
import '../../domain/repositories/insight_feed_repository.dart';
import 'future_view_event.dart';
import 'future_view_state.dart';

class FutureViewBloc extends Bloc<FutureViewEvent, FutureViewState> {
  final InsightFeedRepository _repository;

  FutureViewBloc({required InsightFeedRepository repository})
      : _repository = repository,
        super(const FutureViewInitial()) {
    on<LoadFutureView>(_onLoad);
    on<RefreshFutureView>(_onRefresh);
    on<DismissSuggestion>(_onDismissSuggestion);
    on<DismissAllSuggestions>(_onDismissAll);
    on<AcceptSuggestion>(_onAcceptSuggestion);
    on<AdoptInsight>(_onAdoptInsight);
    on<ConfirmSubItem>(_onConfirmSubItem);
    on<DismissSubItem>(_onDismissSubItem);
    on<DismissSuggestionGroup>(_onDismissSuggestionGroup);
    on<LoadMoreUpcoming>(_onLoadMoreUpcoming);
    on<ToggleTaskDone>(_onToggleTaskDone);
  }

  Future<void> _onLoad(LoadFutureView event, Emitter<FutureViewState> emit) async {
    emit(const FutureViewLoading());
    final result = await _repository.getFutureView();
    result.fold(
      (failure) => emit(FutureViewError(failure.message)),
      (data) => emit(FutureViewLoaded(data: data, lastLoadedAt: DateTime.now())),
    );
  }

  Future<void> _onRefresh(RefreshFutureView event, Emitter<FutureViewState> emit) async {
    final result = await _repository.getFutureView();
    result.fold(
      (failure) {
        if (state is FutureViewLoaded) return;
        emit(FutureViewError(failure.message));
      },
      (data) => emit(FutureViewLoaded(data: data, lastLoadedAt: DateTime.now())),
    );
  }

  Future<void> _onDismissSuggestion(DismissSuggestion event, Emitter<FutureViewState> emit) async {
    if (state is! FutureViewLoaded) return;
    final current = state as FutureViewLoaded;

    if (event.insightId.isNotEmpty) {
      _repository.submitInsightFeedback(
        insightId: event.insightId,
        feedbackType: event.feedbackType,
        reason: event.reason,
      );
    }

    emit(FutureViewLoaded(
      data: current.data,
      dismissedSuggestionIds: {...current.dismissedSuggestionIds, event.insightId},
      lastLoadedAt: current.lastLoadedAt,
    ));
  }

  Future<void> _onDismissAll(DismissAllSuggestions event, Emitter<FutureViewState> emit) async {
    if (state is! FutureViewLoaded) return;
    final current = state as FutureViewLoaded;
    final allIds = current.data.suggestions
        .map((s) => s.insightId.isNotEmpty ? s.insightId : s.id)
        .toSet();

    for (final id in allIds) {
      if (id.isNotEmpty) {
        _repository.submitInsightFeedback(insightId: id, feedbackType: 'not_useful');
      }
    }

    emit(FutureViewLoaded(
      data: current.data,
      dismissedSuggestionIds: {...current.dismissedSuggestionIds, ...allIds},
      lastLoadedAt: current.lastLoadedAt,
    ));
  }

  Future<void> _onDismissSuggestionGroup(DismissSuggestionGroup event, Emitter<FutureViewState> emit) async {
    if (state is! FutureViewLoaded) return;
    final current = state as FutureViewLoaded;

    for (final id in event.insightIds) {
      if (id.isNotEmpty) {
        _repository.submitInsightFeedback(insightId: id, feedbackType: 'not_useful');
      }
    }

    emit(FutureViewLoaded(
      data: current.data,
      dismissedSuggestionIds: {...current.dismissedSuggestionIds, ...event.insightIds},
      lastLoadedAt: current.lastLoadedAt,
    ));
  }

  Future<void> _onAcceptSuggestion(AcceptSuggestion event, Emitter<FutureViewState> emit) async {
    if (state is! FutureViewLoaded) return;
    final current = state as FutureViewLoaded;

    if (event.actionType == 'adopt') {
      // Adopt insight to trip
      final tripId = event.actionData?['related_trip_id'] as String?;
      if (tripId != null && tripId.isNotEmpty && event.insightId.isNotEmpty) {
        await _repository.adoptInsight(
          insightId: event.insightId,
          tripId: tripId,
        );
      }
    } else if (event.actionType == 'acknowledge') {
      // Acknowledge: "我知道了" — 90-day snooze
      if (event.insightId.isNotEmpty) {
        _repository.submitInsightFeedback(
          insightId: event.insightId,
          feedbackType: 'acknowledged',
        );
      }
    } else if (event.actionType == 'confirm_pending_action') {
      final paId = event.actionData?['pending_action_id'] as String?;
      if (paId != null) {
        await _repository.confirmAction(actionId: paId);
      }
    }

    emit(FutureViewLoaded(
      data: current.data,
      dismissedSuggestionIds: {...current.dismissedSuggestionIds, event.insightId},
      lastLoadedAt: current.lastLoadedAt,
    ));

    add(const RefreshFutureView());
  }

  Future<void> _onAdoptInsight(AdoptInsight event, Emitter<FutureViewState> emit) async {
    if (state is! FutureViewLoaded) return;
    final current = state as FutureViewLoaded;

    // Optimistic: dismiss the card
    emit(FutureViewLoaded(
      data: current.data,
      dismissedSuggestionIds: {...current.dismissedSuggestionIds, event.insightId},
      lastLoadedAt: current.lastLoadedAt,
    ));

    await _repository.adoptInsight(
      insightId: event.insightId,
      tripId: event.tripId,
    );

    add(const RefreshFutureView());
  }

  Future<void> _onConfirmSubItem(ConfirmSubItem event, Emitter<FutureViewState> emit) async {
    final subItem = event.subItem;

    if (subItem.isPendingAction) {
      await _repository.confirmAction(actionId: subItem.id);
    } else if (event.relatedTripId != null && event.relatedTripId!.isNotEmpty) {
      await _repository.acceptSuggestionToTrip(
        tripId: event.relatedTripId!,
        itemText: subItem.label,
        insightId: event.insightId,
      );
    }

    // Backend has persisted the change; refresh to reflect new state
    add(const RefreshFutureView());
  }

  Future<void> _onDismissSubItem(DismissSubItem event, Emitter<FutureViewState> emit) async {
    // Local dismissal handled in widget; no backend call needed for now
  }

  Future<void> _onToggleTaskDone(ToggleTaskDone event, Emitter<FutureViewState> emit) async {
    if (state is! FutureViewLoaded) return;
    final current = state as FutureViewLoaded;

    // Optimistic update: toggle locally first
    final updatedTrips = current.data.trips.map((trip) {
      if (trip.id != event.tripId) return trip;
      final updatedTasks = trip.tasks.map((task) {
        if (task.id != event.taskId) return task;
        return FutureViewTripTaskModel(
          id: task.id,
          title: task.title,
          subtitle: task.subtitle,
          done: event.done,
          actionLabel: task.actionLabel,
          actionType: task.actionType,
          isPrimaryAction: task.isPrimaryAction,
          memberColor: task.memberColor,
        );
      }).toList();
      final doneCount = updatedTasks.where((t) => t.done).length;
      return trip.copyWith(tasks: updatedTasks, doneCount: doneCount);
    }).toList();

    emit(FutureViewLoaded(
      data: current.data.copyWith(trips: updatedTrips),
      dismissedSuggestionIds: current.dismissedSuggestionIds,
      lastLoadedAt: current.lastLoadedAt,
    ));

    // Persist to backend
    final result = await _repository.togglePreparationItem(
      tripId: event.tripId,
      taskId: event.taskId,
      done: event.done,
    );

    // Revert on failure
    result.fold(
      (_) => emit(FutureViewLoaded(
        data: current.data,
        dismissedSuggestionIds: current.dismissedSuggestionIds,
        lastLoadedAt: current.lastLoadedAt,
      )),
      (_) {},
    );
  }

  Future<void> _onLoadMoreUpcoming(LoadMoreUpcoming event, Emitter<FutureViewState> emit) async {
    if (state is! FutureViewLoaded) return;
    final current = state as FutureViewLoaded;
    if (!current.data.upcomingHasMore || current.isLoadingMore) return;

    emit(FutureViewLoaded(
      data: current.data,
      dismissedSuggestionIds: current.dismissedSuggestionIds,
      lastLoadedAt: current.lastLoadedAt,
      isLoadingMore: true,
    ));

    final offset = current.data.upcoming.length;
    final result = await _repository.getMoreUpcoming(offset: offset);

    result.fold(
      (_) {
        emit(FutureViewLoaded(
          data: current.data,
          dismissedSuggestionIds: current.dismissedSuggestionIds,
          lastLoadedAt: current.lastLoadedAt,
        ));
      },
      (page) {
        final updatedData = current.data.copyWithMoreUpcoming(
          page.items,
          page.hasMore,
        );
        emit(FutureViewLoaded(
          data: updatedData,
          dismissedSuggestionIds: current.dismissedSuggestionIds,
          lastLoadedAt: current.lastLoadedAt,
        ));
      },
    );
  }
}
