import 'dart:async';

import 'package:flutter_bloc/flutter_bloc.dart';

import '../../data/models/insight_feed_models.dart';
import '../../domain/repositories/insight_feed_repository.dart';
import 'insight_feed_event.dart';
import 'insight_feed_state.dart';

/// BLoC dedicated to insight feed data lifecycle.
///
/// PLAN-001: Decomposed from the original 795-line monolith. Now handles
/// only feed loading, refresh, pagination, expand/collapse, group state,
/// and feedback. Dismiss logic moved to [InsightDismissBloc], action
/// logic moved to [ActionBloc].
class InsightFeedBloc extends Bloc<InsightFeedEvent, InsightFeedState> {
  final InsightFeedRepository _repository;

  /// PLAN-003: Cancellable timers for adopted insight auto-removal.
  /// Keyed by insightId. Cancelled if BLoC closes before timer fires.
  final Map<String, Timer> _adoptionTimers = {};

  InsightFeedBloc({required InsightFeedRepository repository})
      : _repository = repository,
        super(const InsightFeedInitial()) {
    on<LoadInsightFeed>(_onLoadInsightFeed);
    on<RefreshInsightFeed>(_onRefreshInsightFeed);
    on<LoadMoreInsightFeed>(_onLoadMoreInsightFeed);
    on<ExpandInsight>(_onExpandInsight);
    on<CollapseInsight>(_onCollapseInsight);
    on<SubmitInsightFeedback>(_onSubmitInsightFeedback);
    on<ToggleGroupExpand>(_onToggleGroupExpand);
    on<SetShowAllLaterInsights>(_onSetShowAllLaterInsights);
    on<ApplyDefaultGroupExpansion>(_onApplyDefaultGroupExpansion);
    on<RemoveInsightFromFeed>(_onRemoveInsightFromFeed);
    on<RestoreInsightToFeed>(_onRestoreInsightToFeed);
    on<MarkInsightAdopted>(_onMarkInsightAdopted);
  }

  @override
  Future<void> close() {
    for (final timer in _adoptionTimers.values) {
      timer.cancel();
    }
    _adoptionTimers.clear();
    return super.close();
  }

  // ---------------------------------------------------------------------------
  // Load / Refresh
  // ---------------------------------------------------------------------------

  Future<void> _onLoadInsightFeed(
    LoadInsightFeed event,
    Emitter<InsightFeedState> emit,
  ) async {
    emit(const InsightFeedLoadingState());

    final result = await _repository.getInsightFeed(limit: 20);

    result.fold(
      (failure) => emit(InsightFeedErrorState(failure.message)),
      (feed) {
        final loadedState = InsightFeedLoadedState(
          feed: feed,
          nextCursor: feed.nextCursor,
          hasMore: feed.hasMore,
          lastLoadedAt: DateTime.now(),
        );
        if (feed.isGrouped) {
          // PLAN-005: Only expand today_focus by default to reduce
          // cognitive load. Other groups show collapsed with count badge.
          // Server's expandedByDefault is respected only for today_focus
          // or if no today_focus group exists.
          final hasTodayFocus =
              feed.groups.any((g) => g.groupId == 'today_focus');
          final defaultExpanded = hasTodayFocus
              ? {'today_focus'}
              : feed.groups
                  .where((g) => g.expandedByDefault)
                  .map((g) => g.groupId)
                  .toSet();
          emit(loadedState.copyWith(
            expandedGroupIds: defaultExpanded,
            defaultGroupExpansionApplied: true,
          ));
        } else {
          emit(loadedState);
        }
      },
    );
  }

  Future<void> _onRefreshInsightFeed(
    RefreshInsightFeed event,
    Emitter<InsightFeedState> emit,
  ) async {
    final currentState = state;
    if (currentState is InsightFeedLoadedState) {
      emit(currentState.copyWith(isRefreshing: true));
    }

    final result = await _repository.getInsightFeed(limit: 20);

    result.fold(
      (failure) => emit(InsightFeedErrorState(failure.message)),
      (feed) {
        final latestState = state;
        if (latestState is InsightFeedLoadedState) {
          final existingExpanded = latestState.expandedGroupIds;
          final newDefaults = feed.isGrouped
              ? feed.groups
                  .where((g) => g.expandedByDefault)
                  .map((g) => g.groupId)
                  .toSet()
              : <String>{};
          final mergedExpanded = {...existingExpanded, ...newDefaults};

          emit(latestState.copyWith(
            feed: feed,
            isRefreshing: false,
            nextCursor: () => feed.nextCursor,
            hasMore: feed.hasMore,
            isLoadingMore: false,
            expandedGroupIds: mergedExpanded,
            lastLoadedAt: () => DateTime.now(),
            defaultGroupExpansionApplied: true,
          ));
        } else {
          emit(InsightFeedLoadedState(
            feed: feed,
            nextCursor: feed.nextCursor,
            hasMore: feed.hasMore,
            lastLoadedAt: DateTime.now(),
          ));
        }
      },
    );
  }

  Future<void> _onLoadMoreInsightFeed(
    LoadMoreInsightFeed event,
    Emitter<InsightFeedState> emit,
  ) async {
    final currentState = state;
    if (currentState is! InsightFeedLoadedState) return;
    if (currentState.isLoadingMore || !currentState.hasMore) return;

    emit(currentState.copyWith(isLoadingMore: true));

    final result = await _repository.getInsightFeed(
      limit: 20,
      cursor: currentState.nextCursor,
    );

    result.fold(
      (failure) {
        if (isClosed) return;
        final latestState = state;
        if (latestState is InsightFeedLoadedState) {
          emit(latestState.copyWith(isLoadingMore: false));
        }
      },
      (nextPage) {
        if (isClosed) return;
        final latestState = state;
        if (latestState is! InsightFeedLoadedState) return;

        final mergedGroups = _mergeGroupsByGroupId(
          latestState.feed.groups,
          nextPage.groups,
        );

        final mergedFeed = latestState.feed.copyWith(
          groups: mergedGroups,
          insights: [...latestState.feed.insights, ...nextPage.insights],
          nextCursor: () => nextPage.nextCursor,
          hasMore: nextPage.hasMore,
        );
        emit(latestState.copyWith(
          feed: mergedFeed,
          nextCursor: () => nextPage.nextCursor,
          hasMore: nextPage.hasMore,
          isLoadingMore: false,
        ));
      },
    );
  }

  List<InsightGroupModel> _mergeGroupsByGroupId(
    List<InsightGroupModel> existing,
    List<InsightGroupModel> incoming,
  ) {
    if (incoming.isEmpty) return existing;

    final groupMap = <String, InsightGroupModel>{};
    for (final group in existing) {
      groupMap[group.groupId] = group;
    }

    for (final incomingGroup in incoming) {
      final existingGroup = groupMap[incomingGroup.groupId];
      if (existingGroup != null) {
        groupMap[incomingGroup.groupId] = existingGroup.copyWith(
          subtitle: existingGroup.subtitle ?? incomingGroup.subtitle,
          insights: [...existingGroup.insights, ...incomingGroup.insights],
          preparationEvents: [
            ...existingGroup.preparationEvents,
            ...incomingGroup.preparationEvents,
          ],
          standaloneEvents: [
            ...existingGroup.standaloneEvents,
            ...incomingGroup.standaloneEvents,
          ],
          icon: existingGroup.icon ?? incomingGroup.icon,
          accentColor: existingGroup.accentColor ?? incomingGroup.accentColor,
        );
      } else {
        groupMap[incomingGroup.groupId] = incomingGroup;
      }
    }

    final result = <InsightGroupModel>[];
    final addedIds = <String>{};
    for (final group in existing) {
      result.add(groupMap[group.groupId]!);
      addedIds.add(group.groupId);
    }
    for (final group in incoming) {
      if (!addedIds.contains(group.groupId)) {
        result.add(groupMap[group.groupId]!);
        addedIds.add(group.groupId);
      }
    }
    return result;
  }

  // ---------------------------------------------------------------------------
  // Expand / Collapse (individual insight accordion)
  // ---------------------------------------------------------------------------

  void _onExpandInsight(
    ExpandInsight event,
    Emitter<InsightFeedState> emit,
  ) {
    final currentState = state;
    if (currentState is! InsightFeedLoadedState) return;

    if (currentState.expandedInsightId == event.insightId) {
      emit(currentState.copyWith(expandedInsightId: () => null));
    } else {
      emit(currentState.copyWith(expandedInsightId: () => event.insightId));
    }
  }

  void _onCollapseInsight(
    CollapseInsight event,
    Emitter<InsightFeedState> emit,
  ) {
    final currentState = state;
    if (currentState is! InsightFeedLoadedState) return;

    emit(currentState.copyWith(expandedInsightId: () => null));
  }

  // ---------------------------------------------------------------------------
  // Group expand/collapse
  // ---------------------------------------------------------------------------

  void _onToggleGroupExpand(
    ToggleGroupExpand event,
    Emitter<InsightFeedState> emit,
  ) {
    final currentState = state;
    if (currentState is! InsightFeedLoadedState) return;

    final updatedIds = Set<String>.from(currentState.expandedGroupIds);
    if (updatedIds.contains(event.groupId)) {
      updatedIds.remove(event.groupId);
    } else {
      updatedIds.add(event.groupId);
    }
    emit(currentState.copyWith(expandedGroupIds: updatedIds));
  }

  void _onSetShowAllLaterInsights(
    SetShowAllLaterInsights event,
    Emitter<InsightFeedState> emit,
  ) {
    final currentState = state;
    if (currentState is! InsightFeedLoadedState) return;

    emit(currentState.copyWith(showAllLaterInsights: event.show));
  }

  void _onApplyDefaultGroupExpansion(
    ApplyDefaultGroupExpansion event,
    Emitter<InsightFeedState> emit,
  ) {
    final currentState = state;
    if (currentState is! InsightFeedLoadedState) return;
    if (currentState.defaultGroupExpansionApplied) return;

    emit(currentState.copyWith(
      expandedGroupIds: Set<String>.from(event.groupIds),
      defaultGroupExpansionApplied: true,
    ));
  }

  // ---------------------------------------------------------------------------
  // Feed mutation events (driven by dismiss/action blocs)
  // ---------------------------------------------------------------------------

  /// Remove an insight from the feed (called by page when dismiss BLoC fires).
  void _onRemoveInsightFromFeed(
    RemoveInsightFromFeed event,
    Emitter<InsightFeedState> emit,
  ) {
    final currentState = state;
    if (currentState is! InsightFeedLoadedState) return;

    final updatedInsights = currentState.feed.insights
        .where((i) => i.id != event.insightId)
        .toList();

    final updatedGroups = currentState.feed.groups.map((group) {
      if (group.insights.any((i) => i.id == event.insightId)) {
        return group.copyWith(
          insights: group.insights
              .where((i) => i.id != event.insightId)
              .toList(),
        );
      }
      return group;
    }).toList();

    emit(currentState.copyWith(
      feed: currentState.feed.copyWith(
        insights: updatedInsights,
        groups: updatedGroups,
      ),
    ));
  }

  /// Restore a dismissed insight to the feed (undo).
  void _onRestoreInsightToFeed(
    RestoreInsightToFeed event,
    Emitter<InsightFeedState> emit,
  ) {
    final currentState = state;
    if (currentState is! InsightFeedLoadedState) return;

    final restoredInsights = List<InsightFeedItemModel>.from(
      currentState.feed.insights,
    );
    final insertAt = event.originalIndex.clamp(0, restoredInsights.length);
    restoredInsights.insert(insertAt, event.insight);

    final restoredGroups = event.groupId != null
        ? currentState.feed.groups.map((group) {
            if (group.groupId == event.groupId) {
              return group.copyWith(
                insights: [...group.insights, event.insight],
              );
            }
            return group;
          }).toList()
        : currentState.feed.groups;

    emit(currentState.copyWith(
      feed: currentState.feed.copyWith(
        insights: restoredInsights,
        groups: restoredGroups,
      ),
    ));
  }

  /// Mark an insight as adopted (visual change after action confirmed).
  ///
  /// PLAN-003: After the 400ms adoption animation, dispatch [RemoveInsightFromFeed]
  /// via a cancellable Timer to eliminate ghost cards.
  void _onMarkInsightAdopted(
    MarkInsightAdopted event,
    Emitter<InsightFeedState> emit,
  ) {
    final currentState = state;
    if (currentState is! InsightFeedLoadedState) return;

    final updatedAdopted = {...currentState.adoptedInsightIds, event.insightId};
    emit(currentState.copyWith(adoptedInsightIds: updatedAdopted));

    // Cancel any previous timer for this insight (prevent double-removal)
    _adoptionTimers[event.insightId]?.cancel();
    _adoptionTimers[event.insightId] = Timer(
      const Duration(milliseconds: 400),
      () {
        _adoptionTimers.remove(event.insightId);
        if (!isClosed) {
          add(RemoveInsightFromFeed(event.insightId));
        }
      },
    );
  }

  // ---------------------------------------------------------------------------
  // Feedback
  // ---------------------------------------------------------------------------

  Future<void> _onSubmitInsightFeedback(
    SubmitInsightFeedback event,
    Emitter<InsightFeedState> emit,
  ) async {
    final currentState = state;
    if (currentState is! InsightFeedLoadedState) return;

    if (event.feedbackType == 'useful') {
      await _handleUsefulFeedback(event.insightId, currentState, emit);
    } else if (event.feedbackType == 'defer') {
      await _handleDeferFeedback(event.insightId, currentState, emit);
    } else {
      await _handleDismissFeedback(
        event.insightId,
        event.feedbackType,
        currentState,
        emit,
      );
    }
  }

  Future<void> _handleUsefulFeedback(
    String insightId,
    InsightFeedLoadedState currentState,
    Emitter<InsightFeedState> emit,
  ) async {
    final updatedAdopted = {...currentState.adoptedInsightIds, insightId};
    emit(currentState.copyWith(adoptedInsightIds: updatedAdopted));

    // Ephemeral insights (event-context:*) have no DB record — skip API call.
    final isEphemeral = insightId.startsWith('event-context:');
    final bool succeeded;

    if (isEphemeral) {
      succeeded = true;
    } else {
      final result = await _repository.submitInsightFeedback(
        insightId: insightId,
        feedbackType: 'useful',
      );
      succeeded = result.isRight();
      if (!succeeded && !isClosed) {
        emit(currentState);
      }
    }

    // PLAN-003: Only remove from feed after successful feedback.
    if (succeeded) {
      _adoptionTimers[insightId]?.cancel();
      _adoptionTimers[insightId] = Timer(
        const Duration(milliseconds: 400),
        () {
          _adoptionTimers.remove(insightId);
          if (!isClosed) {
            add(RemoveInsightFromFeed(insightId));
          }
        },
      );
    }
  }

  /// Handle 'defer' feedback: submit to backend but keep the card in feed.
  ///
  /// Unlike dismiss/never, defer means "remind me later" — the insight should
  /// stay visible until the user navigates away or a fresh feed loads.
  /// Fire-and-forget: don't block on API response to avoid UI lag.
  Future<void> _handleDeferFeedback(
    String insightId,
    InsightFeedLoadedState currentState,
    Emitter<InsightFeedState> emit,
  ) async {
    // Ephemeral insights have no DB record — nothing to defer.
    if (insightId.startsWith('event-context:')) return;

    // Fire-and-forget: no need to await since defer doesn't change UI state.
    unawaited(_repository.submitInsightFeedback(
      insightId: insightId,
      feedbackType: 'defer',
    ));
  }

  /// Handle non-'useful' feedback types (never, not_useful, dismiss).
  ///
  /// Optimistically removes the insight from the feed, calls the backend API,
  /// and restores the insight on failure. Follows the same pattern as
  /// [_handleUsefulFeedback] for consistency.
  Future<void> _handleDismissFeedback(
    String insightId,
    String feedbackType,
    InsightFeedLoadedState currentState,
    Emitter<InsightFeedState> emit,
  ) async {
    // Capture insight + position before removal for potential restore.
    final allInsights = currentState.allVisibleInsights;
    final originalIndex = allInsights.indexWhere((i) => i.id == insightId);
    final insight = originalIndex >= 0 ? allInsights[originalIndex] : null;
    final groupId = currentState.insightIdToGroupId[insightId];

    // Optimistically remove from feed.
    final updatedInsights = currentState.feed.insights
        .where((i) => i.id != insightId)
        .toList();
    final updatedGroups = currentState.feed.groups.map((group) {
      if (group.insights.any((i) => i.id == insightId)) {
        return group.copyWith(
          insights: group.insights.where((i) => i.id != insightId).toList(),
        );
      }
      return group;
    }).toList();

    emit(currentState.copyWith(
      feed: currentState.feed.copyWith(
        insights: updatedInsights,
        groups: updatedGroups,
      ),
    ));

    // Ephemeral insights have no DB record — skip API call.
    if (insightId.startsWith('event-context:')) return;

    final result = await _repository.submitInsightFeedback(
      insightId: insightId,
      feedbackType: feedbackType,
    );

    // On failure: restore insight to feed and surface error.
    if (result.isLeft() && !isClosed && insight != null) {
      final latestState = state;
      if (latestState is InsightFeedLoadedState) {
        final restoredInsights = List<InsightFeedItemModel>.from(
          latestState.feed.insights,
        );
        final insertAt = originalIndex.clamp(0, restoredInsights.length);
        restoredInsights.insert(insertAt, insight);

        final restoredGroups = groupId != null
            ? latestState.feed.groups.map((group) {
                if (group.groupId == groupId) {
                  return group.copyWith(
                    insights: [...group.insights, insight],
                  );
                }
                return group;
              }).toList()
            : latestState.feed.groups;

        emit(latestState.copyWith(
          feed: latestState.feed.copyWith(
            insights: restoredInsights,
            groups: restoredGroups,
          ),
        ));
      }
    }
  }
}
