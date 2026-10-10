import 'dart:async';

import 'package:flutter_bloc/flutter_bloc.dart';

import '../../domain/repositories/insight_feed_repository.dart';
import 'insight_dismiss_event.dart';
import 'insight_dismiss_state.dart';

/// Dedicated BLoC for the insight dismiss-with-undo lifecycle.
///
/// Extracted from [InsightFeedBloc] (PLAN-001) to separate dismiss logic
/// from feed loading and action execution. Communicates with InsightFeedBloc
/// via StreamSubscription on its state — never via direct BLoC method calls.
///
/// Lifecycle:
/// ```
/// DismissInsight → optimistic remove → 4s timer → CommitDismiss (API)
///                                     ↕ (within 4s)
///                                 UndoDismiss → restore
/// CommitAllDismisses → cancel all timers → batch commit to backend
/// ```
class InsightDismissBloc
    extends Bloc<InsightDismissEvent, InsightDismissState> {
  final InsightFeedRepository _repository;

  /// Active dismiss timers keyed by insightId.
  /// Cancelled on undo or BLoC close.
  final Map<String, Timer> _dismissTimers = {};

  InsightDismissBloc({required InsightFeedRepository repository})
      : _repository = repository,
        super(const InsightDismissIdle()) {
    on<DismissInsight>(_onDismissInsight);
    on<UndoDismiss>(_onUndoDismiss);
    on<CommitDismiss>(_onCommitDismiss);
    on<CommitAllDismisses>(_onCommitAllDismisses);
  }

  @override
  Future<void> close() {
    for (final timer in _dismissTimers.values) {
      timer.cancel();
    }
    _dismissTimers.clear();
    return super.close();
  }

  /// Dismiss an insight with undo support.
  ///
  /// Stores the dismissed insight for positional restore, starts a 4-second
  /// timer. If the timer expires without undo, commits to backend.
  void _onDismissInsight(
    DismissInsight event,
    Emitter<InsightDismissState> emit,
  ) {
    final dismissed = DismissedInsightEntry(
      insight: event.insight,
      dismissedAt: DateTime.now(),
      originalIndex: event.originalIndex,
      groupId: event.groupId,
      feedbackType: event.feedbackType,
    );

    final currentEntries = state.recentlyDismissed;
    emit(InsightDismissActive(
      recentlyDismissed: [...currentEntries, dismissed],
    ));

    // Start 4-second timer
    _dismissTimers[event.insight.id]?.cancel();
    _dismissTimers[event.insight.id] = Timer(
      const Duration(seconds: 4),
      () {
        if (!isClosed) {
          add(CommitDismiss(event.insight.id));
        }
      },
    );
  }

  /// Undo a recent dismiss — remove from pending list.
  void _onUndoDismiss(
    UndoDismiss event,
    Emitter<InsightDismissState> emit,
  ) {
    // Cancel the pending timer
    _dismissTimers[event.insightId]?.cancel();
    _dismissTimers.remove(event.insightId);

    final currentEntries = state.recentlyDismissed;
    final updated = currentEntries
        .where((d) => d.insight.id != event.insightId)
        .toList();

    if (updated.isEmpty) {
      emit(const InsightDismissIdle());
    } else {
      emit(InsightDismissActive(recentlyDismissed: updated));
    }
  }

  /// Commit a single dismissed insight to the backend.
  Future<void> _onCommitDismiss(
    CommitDismiss event,
    Emitter<InsightDismissState> emit,
  ) async {
    _dismissTimers.remove(event.insightId);

    final currentEntries = state.recentlyDismissed;
    // PLAN-003: Retrieve feedbackType before removing from entries list
    final entry = currentEntries.where((d) => d.insight.id == event.insightId).firstOrNull;
    final feedbackType = entry?.feedbackType ?? 'dismiss';

    final updated = currentEntries
        .where((d) => d.insight.id != event.insightId)
        .toList();

    if (updated.isEmpty) {
      emit(const InsightDismissIdle());
    } else {
      emit(InsightDismissActive(recentlyDismissed: updated));
    }

    // Ephemeral insights (event-context:*) have no DB record — skip API call.
    if (!event.insightId.startsWith('event-context:')) {
      await _repository.submitInsightFeedback(
        insightId: event.insightId,
        feedbackType: feedbackType,
      );
    }
  }

  /// Commit all pending dismisses (e.g. on app backgrounding).
  Future<void> _onCommitAllDismisses(
    CommitAllDismisses event,
    Emitter<InsightDismissState> emit,
  ) async {
    // Cancel all timers
    for (final timer in _dismissTimers.values) {
      timer.cancel();
    }
    _dismissTimers.clear();

    final currentEntries = state.recentlyDismissed;
    if (currentEntries.isEmpty) return;

    emit(const InsightDismissIdle());

    // PLAN-012: Parallel batch dismiss via Future.wait
    // PLAN-003: Use per-entry feedbackType to preserve analytics metadata
    await Future.wait(
      currentEntries.map((d) => _repository.submitInsightFeedback(
        insightId: d.insight.id,
        feedbackType: d.feedbackType,
      )),
    );
  }
}
