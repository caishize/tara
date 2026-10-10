import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';

import '../../../../app/router/routes.dart';
import '../../../../app/theme/app_colors.dart';
import '../../data/models/insight_feed_models.dart';
import '../../data/models/kanban_models.dart';
import '../../domain/entities/curated_event.dart';
import '../bloc/action_bloc.dart';
import '../bloc/action_event.dart' as action_events;
import '../bloc/action_state.dart' as action_states;
import '../bloc/insight_dismiss_bloc.dart';
import '../bloc/insight_dismiss_event.dart' as dismiss_events;
import '../bloc/insight_dismiss_state.dart';
import '../bloc/insight_feed_bloc.dart';
import '../bloc/insight_feed_event.dart' as feed_events;
import '../bloc/insight_feed_state.dart';
import '../widgets/action_confirmation_sheet.dart';
import '../widgets/event_mini_card.dart';
import '../widgets/insight_card.dart';
import '../widgets/insight_card_skeleton.dart';
import '../widgets/insight_detail_sheet.dart';
import '../widgets/insight_feed_helpers.dart';
import '../widgets/insight_group_section.dart';
import '../widgets/timeline_event_row.dart';
import 'insight_triage_page.dart';

/// Insight-centric feed page.
///
/// PLAN-001: Coordinates three BLoCs:
/// - [InsightFeedBloc]: feed data lifecycle (load, refresh, pagination, expand)
/// - [InsightDismissBloc]: dismiss-with-undo lifecycle
/// - [ActionBloc]: action creation and confirmation lifecycle
///
/// The page acts as coordinator: dismiss/action BLoC state changes trigger
/// feed mutations via [RemoveInsightFromFeed] / [RestoreInsightToFeed] events.
class InsightFeedPage extends StatefulWidget {
  const InsightFeedPage({super.key});

  @override
  State<InsightFeedPage> createState() => _InsightFeedPageState();
}

class _InsightFeedPageState extends State<InsightFeedPage>
    with WidgetsBindingObserver {
  final ScrollController _scrollController = ScrollController();

  static const _loadMoreThreshold = 200.0;

  @override
  void initState() {
    super.initState();
    _scrollController.addListener(_onScroll);
    WidgetsBinding.instance.addObserver(this);
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _scrollController.removeListener(_onScroll);
    _scrollController.dispose();
    super.dispose();
  }

  /// Commit all pending dismisses when app goes to background.
  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.paused) {
      context
          .read<InsightDismissBloc>()
          .add(const dismiss_events.CommitAllDismisses());
    }
  }

  void _onScroll() {
    if (!_scrollController.hasClients) return;
    final maxScroll = _scrollController.position.maxScrollExtent;
    final currentScroll = _scrollController.position.pixels;
    if (maxScroll - currentScroll <= _loadMoreThreshold) {
      context
          .read<InsightFeedBloc>()
          .add(const feed_events.LoadMoreInsightFeed());
    }
  }

  @override
  Widget build(BuildContext context) {
    return MultiBlocListener(
      listeners: [
        // Listen for action BLoC pending confirmation
        BlocListener<ActionBloc, action_states.ActionState>(
          listenWhen: (prev, curr) =>
              curr is action_states.ActionPendingConfirm &&
              prev is! action_states.ActionPendingConfirm,
          listener: _onActionPendingConfirm,
        ),
        // Listen for action confirmed -> mark adopted in feed
        BlocListener<ActionBloc, action_states.ActionState>(
          listenWhen: (prev, curr) =>
              curr is action_states.ActionConfirmed &&
              prev is! action_states.ActionConfirmed,
          listener: _onActionConfirmed,
        ),
        // Listen for dismiss changes to show undo snackbar
        BlocListener<InsightDismissBloc, InsightDismissState>(
          listenWhen: (prev, curr) {
            return curr.recentlyDismissed.length >
                prev.recentlyDismissed.length;
          },
          listener: _onDismissChanged,
        ),
      ],
      child: BlocBuilder<InsightFeedBloc, InsightFeedState>(
        builder: (context, state) {
          if (state is InsightFeedLoadingState) {
            return const _InsightFeedSkeletonList();
          }
          if (state is InsightFeedErrorState) {
            return InsightErrorState(
              message: state.message,
              onRetry: () => context
                  .read<InsightFeedBloc>()
                  .add(const feed_events.LoadInsightFeed()),
            );
          }
          if (state is InsightFeedLoadedState) {
            // PLAN-002: Use allVisibleInsights for empty state (not feed.isEmpty)
            // so collapsed groups with insights don't falsely trigger empty state.
            final allVisible = state.allVisibleInsights;
            final hasOtherContent = state.feed.standaloneEvents.isNotEmpty ||
                state.feed.laterEvents.isNotEmpty ||
                state.feed.needsPreparation.isNotEmpty;
            if (allVisible.isEmpty && !hasOtherContent) {
              // Returning user = adopted insights this session; new user otherwise
              final isNewUser = state.adoptedInsightIds.isEmpty;
              return InsightEmptyState(isNewUser: isNewUser);
            }
            return state.feed.isGrouped
                ? _buildGroupedFeed(context, state)
                : _buildFlatFeed(context, state);
          }
          return const Center(child: CircularProgressIndicator());
        },
      ),
    );
  }

  /// PLAN-008: Route to inline snackbar or full bottom sheet based on tier.
  void _onActionPendingConfirm(
    BuildContext context,
    action_states.ActionState state,
  ) {
    if (state is! action_states.ActionPendingConfirm) return;

    if (state.confirmationTier == 'inline') {
      // PLAN-012: Inline snackbar with both confirm and cancel actions.
      // SnackBar only supports one action, so both buttons live in content Row.
      // Snackbar priority: action confirmation > dismiss undo (hideCurrentSnackBar
      // clears any pending dismiss undo snackbar before showing this one).
      ScaffoldMessenger.of(context).hideCurrentSnackBar();
      final pendingActionId = state.pendingAction.id;
      final displayText = state.pendingAction.displayTitle.isNotEmpty
          ? state.pendingAction.displayTitle
          : state.pendingAction.description;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Row(
            children: [
              Expanded(
                child: Text(displayText, maxLines: 2, overflow: TextOverflow.ellipsis),
              ),
              const SizedBox(width: 8),
              // Cancel action — dismisses snackbar, does NOT confirm
              TextButton(
                onPressed: () {
                  ScaffoldMessenger.of(context).hideCurrentSnackBar();
                  context.read<ActionBloc>().add(
                        action_events.RejectAction(actionId: pendingActionId),
                      );
                },
                child: Text(
                  '\u53D6\u6D88',
                  style: TextStyle(
                    color: Theme.of(context).colorScheme.onInverseSurface,
                  ),
                ),
              ),
              // Confirm action
              TextButton(
                onPressed: () {
                  ScaffoldMessenger.of(context).hideCurrentSnackBar();
                  context.read<ActionBloc>().add(
                        action_events.ConfirmAction(actionId: pendingActionId),
                      );
                },
                child: Text(
                  '\u786E\u8BA4',
                  style: TextStyle(
                    color: Theme.of(context).colorScheme.primary,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
            ],
          ),
          duration: const Duration(seconds: 8),
        ),
      );
      return;
    }

    // Full: bottom sheet with details
    ActionConfirmationSheet.show(
      context: context,
      pendingAction: state.pendingAction,
      onConfirm: () {
        context.read<ActionBloc>().add(
              action_events.ConfirmAction(actionId: state.pendingAction.id),
            );
      },
      onReject: () {
        context.read<ActionBloc>().add(
              action_events.RejectAction(actionId: state.pendingAction.id),
            );
      },
    );
  }

  void _onActionConfirmed(
    BuildContext context,
    action_states.ActionState state,
  ) {
    if (state is! action_states.ActionConfirmed) return;

    context.read<InsightFeedBloc>().add(
          feed_events.MarkInsightAdopted(state.insightId),
        );
  }

  /// Show undo snackbar when an insight is dismissed.
  void _onDismissChanged(
    BuildContext context,
    InsightDismissState state,
  ) {
    if (state.recentlyDismissed.isEmpty) return;

    final lastDismissed = state.recentlyDismissed.last;
    final pendingCount = state.recentlyDismissed.length;

    ScaffoldMessenger.of(context).hideCurrentSnackBar();
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(
          pendingCount > 1
              ? '\u5DF2\u5FFD\u7565 $pendingCount \u6761\u6D1E\u5BDF'
              : '\u5DF2\u5FFD\u7565',
        ),
        duration: const Duration(seconds: 4),
        action: SnackBarAction(
          label: pendingCount > 1
              ? '\u64A4\u9500\u5168\u90E8'
              : '\u64A4\u9500',
          onPressed: () {
            if (pendingCount > 1) {
              for (final d in state.recentlyDismissed) {
                // Undo in dismiss BLoC
                context
                    .read<InsightDismissBloc>()
                    .add(dismiss_events.UndoDismiss(d.insight.id));
                // Restore in feed BLoC
                context.read<InsightFeedBloc>().add(
                      feed_events.RestoreInsightToFeed(
                        insight: d.insight,
                        originalIndex: d.originalIndex,
                        groupId: d.groupId,
                      ),
                    );
              }
            } else {
              context
                  .read<InsightDismissBloc>()
                  .add(dismiss_events.UndoDismiss(lastDismissed.insight.id));
              context.read<InsightFeedBloc>().add(
                    feed_events.RestoreInsightToFeed(
                      insight: lastDismissed.insight,
                      originalIndex: lastDismissed.originalIndex,
                      groupId: lastDismissed.groupId,
                    ),
                  );
            }
          },
        ),
      ),
    );
  }

  // ---------------------------------------------------------------------------
  // Grouped feed
  // ---------------------------------------------------------------------------

  Widget _buildGroupedFeed(
    BuildContext context,
    InsightFeedLoadedState state,
  ) {
    final feed = state.feed;
    final nonEmptyGroups = feed.groups.where((g) => !g.isEmpty).toList();
    // PLAN-002: Triage entry visible in grouped mode too
    final allInsights = state.allVisibleInsights;
    // PLAN-010: Cache insightIdToGroupId once at build scope — eliminates O(n*m)
    // per-card group search when rendering the full grouped feed.
    final groupIdMap = state.insightIdToGroupId;

    return RefreshIndicator(
      onRefresh: () async {
        context
            .read<InsightFeedBloc>()
            .add(const feed_events.RefreshInsightFeed());
      },
      child: CustomScrollView(
        controller: _scrollController,
        slivers: [
          // PLAN-011: Freshness timestamp + PLAN-002: Triage entry button
          SliverToBoxAdapter(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
              child: Row(
                children: [
                  // PLAN-011: Freshness label on the left
                  if (_freshnessLabel(state.lastLoadedAt) != null)
                    Text(
                      _freshnessLabel(state.lastLoadedAt)!,
                      style: TextStyle(
                        fontSize: 12,
                        color: Theme.of(context).colorScheme.onSurfaceVariant,
                      ),
                    ),
                  const Spacer(),
                  // PLAN-002: Triage button on the right
                  if (allInsights.length >= 3)
                    _TriageEntryButton(
                      onTap: () => _openTriageMode(context),
                    ),
                ],
              ),
            ),
          ),
          for (final group in nonEmptyGroups)
            SliverToBoxAdapter(
              child: InsightGroupSection(
                group: group,
                isExpanded:
                    state.expandedGroupIds.contains(group.groupId),
                onToggle: () => context
                    .read<InsightFeedBloc>()
                    .add(feed_events.ToggleGroupExpand(group.groupId)),
                itemBuilder: (insight) => _buildInsightCard(
                  context,
                  insight,
                  state,
                  groupId: groupIdMap[insight.id],
                ),
                onEventTap: (event) => _navigateToEvent(context, event),
              ),
            ),
          if (feed.laterEvents.isNotEmpty) ...[
            SliverToBoxAdapter(
              child: InsightSectionHeader(
                title: '\u7A0D\u540E\u67E5\u770B',
                emoji: '\uD83D\uDCCB',
                count: feed.laterEvents.length,
              ),
            ),
            SliverList(
              delegate: SliverChildBuilderDelegate(
                (context, index) => TimelineEventRow(
                  event: feed.laterEvents[index],
                  isLast: index == feed.laterEvents.length - 1,
                  onTap: () =>
                      _navigateToEvent(context, feed.laterEvents[index]),
                ),
                childCount: feed.laterEvents.length,
              ),
            ),
          ],
          if (state.isLoadingMore)
            const SliverToBoxAdapter(
              child: Padding(
                padding: EdgeInsets.symmetric(vertical: 16),
                child: Center(
                  child: SizedBox(
                    width: 24,
                    height: 24,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  ),
                ),
              ),
            ),
          const SliverPadding(padding: EdgeInsets.only(bottom: 80)),
        ],
      ),
    );
  }

  // ---------------------------------------------------------------------------
  // Flat feed
  // ---------------------------------------------------------------------------

  Widget _buildFlatFeed(
    BuildContext context,
    InsightFeedLoadedState state,
  ) {
    final feed = state.feed;
    // PLAN-010: Cache insightIdToGroupId once at build scope
    final groupIdMap = state.insightIdToGroupId;

    final insights = feed.insights;
    assert(
      _isServerSorted(insights),
      'Server returned unsorted flat feed. '
      'Expected insights sorted by urgency (urgent > important > normal).',
    );

    final nowInsights = insights
        .where((i) => i.urgency == 'urgent' || i.urgency == 'important')
        .toList();
    final laterInsights =
        insights.where((i) => i.urgency == 'normal').toList();

    final hasLaterSection =
        laterInsights.isNotEmpty || feed.laterEvents.isNotEmpty;
    final laterDisplayCount = state.showAllLaterInsights
        ? laterInsights.length
        : laterInsights.take(3).length;

    return RefreshIndicator(
      onRefresh: () async {
        context
            .read<InsightFeedBloc>()
            .add(const feed_events.RefreshInsightFeed());
      },
      child: CustomScrollView(
        controller: _scrollController,
        slivers: [
          SliverToBoxAdapter(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: InsightSectionHeader(
                        title: '\u73B0\u5728\u5173\u6CE8',
                        emoji: '\u2728',
                        count: nowInsights.length + feed.standaloneEvents.length,
                      ),
                    ),
                    // PLAN-002: Triage mode entry button — use allVisibleInsights
                    if (state.allVisibleInsights.length >= 3)
                      Padding(
                        padding: const EdgeInsets.only(right: 16),
                        child: _TriageEntryButton(
                          onTap: () => _openTriageMode(context),
                        ),
                      ),
                  ],
                ),
                // PLAN-011: Freshness timestamp below header
                if (_freshnessLabel(state.lastLoadedAt) != null)
                  Padding(
                    padding: const EdgeInsets.only(left: 16, bottom: 4),
                    child: Text(
                      _freshnessLabel(state.lastLoadedAt)!,
                      style: TextStyle(
                        fontSize: 12,
                        color: Theme.of(context).colorScheme.onSurfaceVariant,
                      ),
                    ),
                  ),
              ],
            ),
          ),
          SliverList(
            delegate: SliverChildBuilderDelegate(
              (context, index) => _buildInsightCard(
                context,
                nowInsights[index],
                state,
                groupId: groupIdMap[nowInsights[index].id],
                insightIndex: insights.indexOf(nowInsights[index]),
              ),
              childCount: nowInsights.length,
            ),
          ),
          if (feed.standaloneEvents.isNotEmpty)
            SliverList(
              delegate: SliverChildBuilderDelegate(
                (context, index) => Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: EventMiniCard(
                    event: feed.standaloneEvents[index],
                    onTap: () => _navigateToEvent(
                        context, feed.standaloneEvents[index]),
                  ),
                ),
                childCount: feed.standaloneEvents.length,
              ),
            ),
          if (hasLaterSection)
            SliverToBoxAdapter(
              child: InsightSectionHeader(
                title: '\u7A0D\u540E\u67E5\u770B',
                emoji: '\uD83D\uDCCB',
                count: laterInsights.length + feed.laterEvents.length,
              ),
            ),
          if (laterInsights.isNotEmpty)
            SliverList(
              delegate: SliverChildBuilderDelegate(
                (context, index) => _buildInsightCard(
                  context,
                  laterInsights[index],
                  state,
                  groupId: groupIdMap[laterInsights[index].id],
                  insightIndex: insights.indexOf(laterInsights[index]),
                ),
                childCount: laterDisplayCount,
              ),
            ),
          if (laterInsights.length > 3 && !state.showAllLaterInsights)
            SliverToBoxAdapter(
              child: InsightShowMoreButton(
                onTap: () => context
                    .read<InsightFeedBloc>()
                    .add(const feed_events.SetShowAllLaterInsights(true)),
                remaining: laterInsights.length - 3,
              ),
            ),
          if (feed.laterEvents.isNotEmpty)
            SliverList(
              delegate: SliverChildBuilderDelegate(
                (context, index) => TimelineEventRow(
                  event: feed.laterEvents[index],
                  isLast: index == feed.laterEvents.length - 1,
                  onTap: () =>
                      _navigateToEvent(context, feed.laterEvents[index]),
                ),
                childCount: feed.laterEvents.length,
              ),
            ),
          if (state.isLoadingMore)
            const SliverToBoxAdapter(
              child: Padding(
                padding: EdgeInsets.symmetric(vertical: 16),
                child: Center(
                  child: SizedBox(
                    width: 24,
                    height: 24,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  ),
                ),
              ),
            ),
          const SliverPadding(padding: EdgeInsets.only(bottom: 80)),
        ],
      ),
    );
  }

  // ---------------------------------------------------------------------------
  // PLAN-011: Feed freshness timestamp
  // ---------------------------------------------------------------------------

  /// Returns "N分钟前更新" based on [lastLoadedAt], or null if not available.
  String? _freshnessLabel(DateTime? lastLoadedAt) {
    if (lastLoadedAt == null) return null;
    final diff = DateTime.now().difference(lastLoadedAt);
    if (diff.inMinutes < 1) return '刚刚更新';
    if (diff.inMinutes < 60) return '${diff.inMinutes}分钟前更新';
    if (diff.inHours < 24) return '${diff.inHours}小时前更新';
    return '今天更新';
  }

  bool _isServerSorted(List<InsightFeedItemModel> insights) {
    if (insights.length <= 1) return true;
    const urgencyRank = {'urgent': 0, 'important': 1, 'normal': 2};
    for (int i = 0; i < insights.length - 1; i++) {
      final currRank = urgencyRank[insights[i].urgency] ?? 2;
      final nextRank = urgencyRank[insights[i + 1].urgency] ?? 2;
      if (currRank > nextRank) return false;
    }
    return true;
  }

  // ---------------------------------------------------------------------------
  // Shared: insight card builder
  // ---------------------------------------------------------------------------

  /// Builds a single insight card with BlocSelector for expand/adopt isolation
  /// and RepaintBoundary for dismiss animation containment.
  ///
  /// PLAN-010: [groupId] and [insightIndex] are pre-computed by the caller
  /// from the cached [InsightFeedLoadedState.insightIdToGroupId] map, avoiding
  /// O(n*m) group search per card rebuild.
  Widget _buildInsightCard(
    BuildContext context,
    InsightFeedItemModel insight,
    InsightFeedLoadedState state, {
    String? groupId,
    int? insightIndex,
  }) {
    // PLAN-010: Use provided values or fall back to linear search
    final resolvedGroupId = groupId;
    final resolvedIndex = insightIndex ?? state.feed.insights.indexOf(insight);

    final isAdopted = state.adoptedInsightIds.contains(insight.id);

    // PLAN-010: BlocSelector isolates expand state — only this card rebuilds
    // when expandedInsightId changes, not the entire feed.
    final card = BlocSelector<InsightFeedBloc, InsightFeedState, bool>(
      selector: (feedState) =>
          feedState is InsightFeedLoadedState &&
          feedState.expandedInsightId == insight.id,
      builder: (context, isExpanded) => InsightCard(
        insight: insight,
        isExpanded: isExpanded,
        onTap: () => context
            .read<InsightFeedBloc>()
            .add(feed_events.ExpandInsight(insight.id)),
        onDismiss: () {
          // Coordinate: dismiss BLoC tracks undo, feed BLoC removes from list
          context.read<InsightDismissBloc>().add(
                dismiss_events.DismissInsight(
                  insight: insight,
                  originalIndex: resolvedIndex >= 0 ? resolvedIndex : 0,
                  groupId: resolvedGroupId,
                ),
              );
          context
              .read<InsightFeedBloc>()
              .add(feed_events.RemoveInsightFromFeed(insight.id));
        },
        onActionTap: (actionType, actionData) {
          // Navigational actions: route directly without ActionBloc
          // (ActionBloc marks the card "adopted" which hides it).
          if (actionType == 'open_event_detail') {
            final eventId = actionData?['event_id'];
            if (eventId != null) {
              context.push(Routes.eventDetail(eventId.toString()));
            }
            return;
          }
          if (actionType == 'open_trip_detail') {
            final tripId = actionData?['trip_id'];
            if (tripId != null) {
              context.push(Routes.tripDetail(tripId.toString()));
            }
            return;
          }
          context.read<ActionBloc>().add(action_events.RequestAction(
                insightId: insight.id,
                actionType: actionType,
                actionData: actionData,
              ));
        },
        onDefer: () {
          context.read<InsightFeedBloc>().add(
                feed_events.SubmitInsightFeedback(
                  insightId: insight.id,
                  feedbackType: 'defer',
                ),
              );
          ScaffoldMessenger.of(context).hideCurrentSnackBar();
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text('已暂缓，4小时后提醒'),
              duration: Duration(seconds: 3),
            ),
          );
        },
        onEventTap: (eventId) => context.push(Routes.eventDetail(eventId)),
        onMemberTap: (memberId) =>
            context.push(Routes.memberDetail(memberId)),
        onShowDetail: () => InsightDetailSheet.show(
          context,
          insight: insight,
          onFeedback: (feedbackType) {
            context.read<InsightFeedBloc>().add(
                  feed_events.SubmitInsightFeedback(
                    insightId: insight.id,
                    feedbackType: feedbackType,
                  ),
                );
          },
          onActionTap: (actionType, actionData) {
            // Navigational actions: route directly without ActionBloc
            // (same bypass as card's onActionTap to avoid MarkInsightAdopted).
            if (actionType == 'open_event_detail') {
              final eventId = actionData?['event_id'];
              if (eventId != null) {
                context.push(Routes.eventDetail(eventId.toString()));
              }
              return;
            }
            if (actionType == 'open_trip_detail') {
              final tripId = actionData?['trip_id'];
              if (tripId != null) {
                context.push(Routes.tripDetail(tripId.toString()));
              }
              return;
            }
            context.read<ActionBloc>().add(action_events.RequestAction(
                  insightId: insight.id,
                  actionType: actionType,
                  actionData: actionData,
                ));
          },
          onEventTap: (eventId) => context.push(Routes.eventDetail(eventId)),
          onMemberTap: (memberId) =>
              context.push(Routes.memberDetail(memberId)),
        ),
      ),
    );

    // PLAN-010: RepaintBoundary wraps the Dismissible container (inside InsightCard)
    // so dismiss animations are contained and don't trigger full-feed repaint.
    final bounded = RepaintBoundary(child: card);

    if (isAdopted) {
      return _AdoptedInsightOverlay(child: bounded);
    }
    return bounded;
  }

  // ---------------------------------------------------------------------------
  // PLAN-009: Triage mode
  // ---------------------------------------------------------------------------

  void _openTriageMode(BuildContext context) {
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => MultiBlocProvider(
          providers: [
            BlocProvider.value(value: context.read<InsightFeedBloc>()),
            BlocProvider.value(value: context.read<InsightDismissBloc>()),
            BlocProvider.value(value: context.read<ActionBloc>()),
          ],
          child: const InsightTriagePage(),
        ),
      ),
    );
  }

  // ---------------------------------------------------------------------------
  // Navigation
  // ---------------------------------------------------------------------------

  void _navigateToEvent(BuildContext context, KanbanEventModel event) {
    final eventType = event.eventType;
    if (eventType == CuratedEventType.businessTrip ||
        eventType == CuratedEventType.travel) {
      if (event.tripId != null) {
        context.push(Routes.tripDetail(event.tripId!));
        return;
      }
    }
    context.push(Routes.eventDetail(event.id), extra: event);
  }
}

/// PLAN-010: Adopted insight overlay with checkmark + green border + slide.
class _AdoptedInsightOverlay extends StatefulWidget {
  final Widget child;

  const _AdoptedInsightOverlay({required this.child});

  @override
  State<_AdoptedInsightOverlay> createState() => _AdoptedInsightOverlayState();
}

class _AdoptedInsightOverlayState extends State<_AdoptedInsightOverlay>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;
  late final Animation<double> _opacityAnim;
  late final Animation<Offset> _slideAnim;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 400),
    )..forward();
    _opacityAnim = Tween<double>(begin: 1.0, end: 0.4).animate(
      CurvedAnimation(parent: _controller, curve: Curves.easeOut),
    );
    _slideAnim = Tween<Offset>(
      begin: Offset.zero,
      end: const Offset(0.02, 0),
    ).animate(
      CurvedAnimation(parent: _controller, curve: Curves.easeOut),
    );
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return SlideTransition(
      position: _slideAnim,
      child: FadeTransition(
        opacity: _opacityAnim,
        child: Stack(
          children: [
            Container(
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(16),
                border: Border.all(
                  color: AppColors.success.withValues(alpha: 0.3),
                  width: 2,
                ),
              ),
              child: widget.child,
            ),
            Positioned(
              top: 12,
              right: 28,
              child: Container(
                padding: const EdgeInsets.all(4),
                decoration: BoxDecoration(
                  color: AppColors.success.withValues(alpha: 0.9),
                  shape: BoxShape.circle,
                ),
                child: const Icon(
                  Icons.check,
                  size: 16,
                  color: Colors.white,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// PLAN-009: Compact triage mode entry button.
class _TriageEntryButton extends StatelessWidget {
  final VoidCallback onTap;

  const _TriageEntryButton({required this.onTap});

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;

    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
        decoration: BoxDecoration(
          color: colorScheme.primaryContainer,
          borderRadius: BorderRadius.circular(16),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              Icons.swipe,
              size: 14,
              color: colorScheme.onPrimaryContainer,
            ),
            const SizedBox(width: 4),
            Text(
              '\u5FEB\u901F\u5206\u62E3',
              style: TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.w600,
                color: colorScheme.onPrimaryContainer,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// Renders 3 shimmer skeleton cards during the loading state.
class _InsightFeedSkeletonList extends StatelessWidget {
  const _InsightFeedSkeletonList();

  @override
  Widget build(BuildContext context) {
    return ListView(
      physics: const NeverScrollableScrollPhysics(),
      padding: const EdgeInsets.only(top: 8),
      children: const [
        InsightCardSkeleton(),
        InsightCardSkeleton(),
        InsightCardSkeleton(),
      ],
    );
  }
}
