import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';
import 'package:url_launcher/url_launcher.dart';
import '../../../../app/router/routes.dart';
import '../../../../app/theme/app_colors.dart';
import '../bloc/future_view_bloc.dart';
import '../bloc/future_view_event.dart';
import '../bloc/future_view_state.dart';
import '../widgets/future_section_header.dart';
import '../widgets/future_trip_card.dart';
import '../widgets/future_suggestion_card.dart';
import '../widgets/future_suggestion_group_card.dart';
import '../widgets/future_upcoming_row.dart';
import '../widgets/future_family_row.dart';
import '../widgets/future_footer.dart';
import '../widgets/future_view_skeleton.dart';
import '../../data/models/insight_feed_models.dart';
import '../../data/models/future_view_models.dart';

class FutureViewPage extends StatelessWidget {
  const FutureViewPage({super.key});

  @override
  Widget build(BuildContext context) {
    return BlocBuilder<FutureViewBloc, FutureViewState>(
      builder: (context, state) {
        if (state is FutureViewLoading) {
          return const FutureViewSkeleton();
        }
        if (state is FutureViewError) {
          return _buildError(context, state.message);
        }
        if (state is FutureViewLoaded) {
          return _buildContent(context, state);
        }
        return const SizedBox.shrink();
      },
    );
  }

  Widget _buildError(BuildContext context, String message) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Icon(Icons.error_outline, size: 48, color: AppColors.error),
          const SizedBox(height: 12),
          Text(message, style: const TextStyle(fontSize: 14, color: AppColors.textSecondary)),
          const SizedBox(height: 16),
          TextButton(
            onPressed: () => context.read<FutureViewBloc>().add(const LoadFutureView()),
            child: const Text('重试'),
          ),
        ],
      ),
    );
  }

  Widget _buildContent(BuildContext context, FutureViewLoaded state) {
    final data = state.data;
    final visibleSuggestions = data.suggestions
        .where((s) {
          final key = s.insightId.isNotEmpty ? s.insightId : s.id;
          return !state.dismissedSuggestionIds.contains(key);
        })
        .toList();
    final suggestionGroups = groupSuggestionsByKey(visibleSuggestions);

    return RefreshIndicator(
      onRefresh: () async {
        context.read<FutureViewBloc>().add(const RefreshFutureView());
      },
      child: CustomScrollView(
        slivers: [
          // ---- 近期行程 ----
          if (data.trips.isNotEmpty) ...[
            SliverToBoxAdapter(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(16, 8, 16, 12),
                child: FutureSectionHeader(
                  icon: Icons.luggage_outlined,
                  iconColor: AppColors.accentGreen,
                  title: '近期行程',
                  count: data.trips.length,
                  countColor: AppColors.accentGreen,
                ),
              ),
            ),
            SliverList(
              delegate: SliverChildBuilderDelegate(
                (context, index) {
                  final trip = data.trips[index];
                  return Padding(
                    padding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
                    child: FutureTripCard(
                      trip: trip,
                      onTap: () => context.push(Routes.tripDetail(trip.id)),
                      onTaskToggle: (taskId, done) {
                        context.read<FutureViewBloc>().add(
                          ToggleTaskDone(tripId: trip.id, taskId: taskId, done: done),
                        );
                      },
                      onInsightDismiss: (insight) async {
                        context.read<FutureViewBloc>().add(
                          DismissSuggestion(insight.id),
                        );
                        return true;
                      },
                      onInsightActionTap: (insight, actionType, payload) {
                        _handleInsightAction(
                          context,
                          insightId: insight.id,
                          actionType: actionType,
                          payload: payload,
                          relatedTripId: trip.id,
                          insightTitle: insight.title,
                        );
                      },
                    ),
                  );
                },
                childCount: data.trips.length,
              ),
            ),
          ],

          // ---- Divider ----
          if (data.trips.isNotEmpty && suggestionGroups.isNotEmpty)
            const SliverToBoxAdapter(
              child: Padding(
                padding: EdgeInsets.symmetric(horizontal: 16),
                child: Divider(height: 1, color: AppColors.divider),
              ),
            ),

          // ---- AI 建议 (grouped) ----
          if (suggestionGroups.isNotEmpty) ...[
            SliverToBoxAdapter(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(16, 16, 16, 12),
                child: FutureSectionHeader(
                  icon: Icons.auto_awesome,
                  iconColor: const Color(0xFF7B1FA2),
                  title: 'AI 建议',
                  trailingText: '全部忽略',
                  onTrailingTap: () {
                    context.read<FutureViewBloc>().add(const DismissAllSuggestions());
                  },
                ),
              ),
            ),
            SliverList(
              delegate: SliverChildBuilderDelegate(
                (context, index) {
                  final group = suggestionGroups[index];

                  if (group.isSingleItem) {
                    final suggestion = group.suggestions.first;
                    return Padding(
                      padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
                      child: FutureSuggestionCard(
                        suggestion: suggestion,
                        onAction: () => _handleSuggestionAction(context, suggestion),
                        onDismiss: () => _dismissSuggestion(context, suggestion),
                        onDismissWithFeedback: (feedbackType) {
                          context.read<FutureViewBloc>().add(
                            DismissSuggestion(
                              suggestion.insightId.isNotEmpty
                                  ? suggestion.insightId
                                  : suggestion.id,
                              feedbackType: feedbackType,
                            ),
                          );
                        },
                        onSubItemConfirm: (subItem) {
                          context.read<FutureViewBloc>().add(
                            ConfirmSubItem(
                              subItem,
                              relatedTripId: suggestion.relatedTripId,
                              insightId: suggestion.insightId,
                            ),
                          );
                        },
                        onSubItemDismiss: (subItem) {
                          context.read<FutureViewBloc>().add(
                            DismissSubItem(subItem),
                          );
                        },
                        onNavigateTrip: () {
                          final tripId = suggestion.relatedTripId;
                          if (tripId != null && tripId.isNotEmpty) {
                            context.push(Routes.tripDetail(tripId));
                          }
                        },
                        onActionOptionTap: (actionOption) {
                          _handleActionOption(context, suggestion, actionOption);
                        },
                      ),
                    );
                  }

                  // Multi-item group → accordion card
                  return Padding(
                    padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
                    child: FutureSuggestionGroupCard(
                      group: group,
                      onAction: (s) => _handleSuggestionAction(context, s),
                      onDismiss: (s) => _dismissSuggestion(context, s),
                      onDismissWithFeedback: (s, feedbackType) {
                        context.read<FutureViewBloc>().add(
                          DismissSuggestion(
                            s.insightId.isNotEmpty ? s.insightId : s.id,
                            feedbackType: feedbackType,
                          ),
                        );
                      },
                      onActionOptionTap: (s, actionOption) {
                        _handleActionOption(context, s, actionOption);
                      },
                      onDismissGroup: () {
                        context.read<FutureViewBloc>().add(
                          DismissSuggestionGroup(group.allInsightIds),
                        );
                      },
                    ),
                  );
                },
                childCount: suggestionGroups.length,
              ),
            ),
          ],

          // ---- Divider ----
          if ((data.trips.isNotEmpty || suggestionGroups.isNotEmpty) && data.upcoming.isNotEmpty)
            const SliverToBoxAdapter(
              child: Padding(
                padding: EdgeInsets.symmetric(horizontal: 16),
                child: Divider(height: 1, color: AppColors.divider),
              ),
            ),

          // ---- 即将到来 ----
          if (data.upcoming.isNotEmpty) ...[
            SliverToBoxAdapter(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(16, 16, 16, 12),
                child: FutureSectionHeader(
                  icon: Icons.calendar_today,
                  iconColor: const Color(0xFFD4A64A),
                  title: '即将到来',
                  count: data.upcoming.length,
                  countColor: const Color(0xFFD4A64A),
                ),
              ),
            ),
            SliverToBoxAdapter(
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16),
                child: Container(
                  clipBehavior: Clip.hardEdge,
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(16),
                    border: Border.all(color: AppColors.divider),
                    boxShadow: [
                      BoxShadow(
                        color: const Color(0xFF1A1918).withValues(alpha: 0.03),
                        blurRadius: 6,
                        offset: const Offset(0, 1),
                      ),
                    ],
                  ),
                  child: Column(
                    children: [
                      for (int i = 0; i < data.upcoming.length; i++)
                        FutureUpcomingRow(
                          item: data.upcoming[i],
                          isLast: i == data.upcoming.length - 1 && !data.upcomingHasMore,
                          onTap: () => _onUpcomingTap(context, data.upcoming[i]),
                        ),
                      // Load more button
                      if (data.upcomingHasMore)
                        _buildLoadMoreButton(context, state.isLoadingMore),
                    ],
                  ),
                ),
              ),
            ),
          ],

          // ---- Divider ----
          if (data.upcoming.isNotEmpty && data.familyMembers.isNotEmpty)
            const SliverToBoxAdapter(
              child: Padding(
                padding: EdgeInsets.fromLTRB(16, 16, 16, 0),
                child: Divider(height: 1, color: AppColors.divider),
              ),
            ),

          // ---- 家庭关注 ----
          if (data.familyMembers.isNotEmpty) ...[
            const SliverToBoxAdapter(
              child: Padding(
                padding: EdgeInsets.fromLTRB(16, 16, 16, 12),
                child: FutureSectionHeader(
                  icon: Icons.favorite,
                  iconColor: AppColors.accentWarm,
                  title: '家庭关注',
                ),
              ),
            ),
            SliverToBoxAdapter(
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16),
                child: Container(
                  clipBehavior: Clip.hardEdge,
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(16),
                    border: Border.all(color: AppColors.divider),
                    boxShadow: [
                      BoxShadow(
                        color: const Color(0xFF1A1918).withValues(alpha: 0.03),
                        blurRadius: 6,
                        offset: const Offset(0, 1),
                      ),
                    ],
                  ),
                  child: Column(
                    children: [
                      for (int i = 0; i < data.familyMembers.length; i++) ...[
                        FutureFamilyRow(
                          member: data.familyMembers[i],
                          onTap: () => context.push(Routes.memberDetail(data.familyMembers[i].id)),
                        ),
                        if (i < data.familyMembers.length - 1)
                          const Padding(
                            padding: EdgeInsets.symmetric(vertical: 7),
                            child: Divider(height: 1, color: AppColors.divider),
                          ),
                      ],
                    ],
                  ),
                ),
              ),
            ),
          ],

          // ---- Footer ----
          const SliverToBoxAdapter(child: FutureFooter()),
          const SliverPadding(padding: EdgeInsets.only(bottom: 80)),
        ],
      ),
    );
  }

  Widget _buildLoadMoreButton(BuildContext context, bool isLoading) {
    return GestureDetector(
      onTap: isLoading
          ? null
          : () => context.read<FutureViewBloc>().add(const LoadMoreUpcoming()),
      behavior: HitTestBehavior.opaque,
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 12),
        decoration: const BoxDecoration(
          border: Border(
            top: BorderSide(color: AppColors.divider, width: 1),
          ),
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            if (isLoading)
              const SizedBox(
                width: 14,
                height: 14,
                child: CircularProgressIndicator(strokeWidth: 2),
              )
            else ...[
              const Text(
                '加载更多',
                style: TextStyle(
                  fontSize: 12,
                  color: AppColors.textTertiary,
                  height: 1.2,
                ),
              ),
              const SizedBox(width: 4),
              const Icon(
                Icons.keyboard_arrow_down,
                size: 14,
                color: AppColors.textTertiary,
              ),
            ],
          ],
        ),
      ),
    );
  }

  void _handleSuggestionAction(
    BuildContext context,
    FutureViewSuggestionModel suggestion,
  ) {
    final bloc = context.read<FutureViewBloc>();
    if (suggestion.hasTripContext && suggestion.relatedTripId != null) {
      bloc.add(AcceptSuggestion(
        insightId: suggestion.insightId,
        actionType: 'adopt',
        actionData: {'related_trip_id': suggestion.relatedTripId},
      ));
    } else if (suggestion.actionType == 'confirm_pending_action') {
      bloc.add(AcceptSuggestion(
        insightId: suggestion.insightId,
        actionType: 'confirm_pending_action',
        actionData: suggestion.actionData,
      ));
    } else {
      bloc.add(AcceptSuggestion(
        insightId: suggestion.insightId,
        actionType: 'acknowledge',
      ));
    }
  }

  void _dismissSuggestion(
    BuildContext context,
    FutureViewSuggestionModel suggestion,
  ) {
    context.read<FutureViewBloc>().add(
      DismissSuggestion(
        suggestion.insightId.isNotEmpty ? suggestion.insightId : suggestion.id,
      ),
    );
  }

  void _handleActionOption(
    BuildContext context,
    FutureViewSuggestionModel suggestion,
    ActionOptionModel actionOption,
  ) {
    final insightId = suggestion.insightId.isNotEmpty
        ? suggestion.insightId
        : suggestion.id;

    _handleInsightAction(
      context,
      insightId: insightId,
      actionType: actionOption.actionType,
      payload: {
        ...suggestion.actionData ?? const {},
        ...actionOption.payload,
      },
      relatedTripId: suggestion.relatedTripId,
      insightTitle: suggestion.title,
      actionLabel: actionOption.label,
    );
  }

  /// Unified action handler for both AI建议 and trip insight action buttons.
  void _handleInsightAction(
    BuildContext context, {
    required String insightId,
    required String actionType,
    Map<String, dynamic>? payload,
    String? relatedTripId,
    String? insightTitle,
    String? actionLabel,
  }) {
    final bloc = context.read<FutureViewBloc>();

    switch (actionType) {
      // ── Adopt to trip ──
      case 'adopt':
        final tripId = payload?['related_trip_id'] as String?
            ?? payload?['trip_id'] as String?
            ?? relatedTripId;
        bloc.add(AcceptSuggestion(
          insightId: insightId,
          actionType: 'adopt',
          actionData: {'related_trip_id': tripId, ...?payload},
        ));
        _showFeedback(context, '已采纳到行程');

      // ── Navigate to conversation ──
      case 'open_chat':
      case 'send_care_message':
      case 'send_message':
        bloc.add(AcceptSuggestion(
          insightId: insightId,
          actionType: 'acknowledge',
          actionData: payload,
        ));
        context.go(Routes.conversation);

      // ── Navigate to trip detail ──
      case 'open_detail':
      case 'open_trip_detail':
        final tripId = payload?['related_trip_id'] as String?
            ?? payload?['trip_id'] as String?
            ?? relatedTripId;
        if (tripId != null && tripId.isNotEmpty) {
          bloc.add(AcceptSuggestion(
            insightId: insightId,
            actionType: 'acknowledge',
            actionData: payload,
          ));
          context.push(Routes.tripDetail(tripId));
        } else {
          // No trip context — navigate to chat
          bloc.add(AcceptSuggestion(
            insightId: insightId,
            actionType: 'acknowledge',
            actionData: payload,
          ));
          context.go(Routes.conversation);
        }

      // ── Schedule / meeting actions → navigate to chat ──
      case 'create_pending_action':
      case 'suggest_meeting':
      case 'schedule_meeting':
        bloc.add(AcceptSuggestion(
          insightId: insightId,
          actionType: 'acknowledge',
          actionData: payload,
        ));
        context.go(Routes.conversation);

      // ── Gift actions → navigate to gift page or chat ──
      case 'suggest_gift':
      case 'prepare_gift':
        final memberId = payload?['member_id'] as String?
            ?? payload?['recipient_id'] as String?;
        bloc.add(AcceptSuggestion(
          insightId: insightId,
          actionType: 'acknowledge',
          actionData: payload,
        ));
        if (memberId != null && memberId.isNotEmpty) {
          context.push(Routes.giftRecommend(memberId));
        } else {
          context.go(Routes.conversation);
        }

      // ── Greeting generation → navigate to chat ──
      case 'generate_greeting':
      case 'suggest_greeting':
        bloc.add(AcceptSuggestion(
          insightId: insightId,
          actionType: 'acknowledge',
          actionData: payload,
        ));
        context.go(Routes.conversation);

      // ── Set reminder → navigate to chat ──
      case 'set_reminder':
        bloc.add(AcceptSuggestion(
          insightId: insightId,
          actionType: 'acknowledge',
          actionData: payload,
        ));
        context.go(Routes.conversation);

      // ── Phone call action ──
      case 'call_family':
        final phone = payload?['phone'] as String?
            ?? payload?['phone_number'] as String?;
        if (phone != null && phone.isNotEmpty) {
          launchUrl(Uri(scheme: 'tel', path: phone));
        } else {
          // No phone number — fall back to chat
          context.go(Routes.conversation);
        }
        bloc.add(AcceptSuggestion(
          insightId: insightId,
          actionType: 'acknowledge',
          actionData: payload,
        ));

      // ── Snooze ──
      case 'snooze':
        bloc.add(AcceptSuggestion(
          insightId: insightId,
          actionType: 'acknowledge',
          actionData: payload,
        ));
        _showFeedback(context, '已设置稍后提醒');

      // ── Acknowledge / share / create_memory ──
      case 'acknowledge':
      case 'share':
      case 'create_memory':
        bloc.add(AcceptSuggestion(
          insightId: insightId,
          actionType: 'acknowledge',
          actionData: payload,
        ));
        _showFeedback(context, '已记录');

      // ── Confirm pending action ──
      case 'confirm_pending_action':
        bloc.add(AcceptSuggestion(
          insightId: insightId,
          actionType: 'confirm_pending_action',
          actionData: payload,
        ));
        _showFeedback(context, '已确认执行');

      // ── Dismiss ──
      case 'dismiss':
        bloc.add(DismissSuggestion(insightId));

      // ── Default: acknowledge + show feedback ──
      default:
        bloc.add(AcceptSuggestion(
          insightId: insightId,
          actionType: actionType,
          actionData: payload,
        ));
        _showFeedback(context, '已处理');
    }
  }

  void _showFeedback(BuildContext context, String message) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        duration: const Duration(seconds: 2),
        behavior: SnackBarBehavior.floating,
      ),
    );
  }

  void _onUpcomingTap(BuildContext context, FutureViewUpcomingModel item) {
    showModalBottomSheet<void>(
      context: context,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (ctx) => Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              '${item.emoji} ${item.title}',
              style: const TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.w600,
                color: AppColors.textPrimary,
              ),
            ),
            const SizedBox(height: 8),
            if (item.contextHint.isNotEmpty)
              Text(
                item.contextHint,
                style: const TextStyle(
                  fontSize: 14,
                  color: AppColors.textSecondary,
                ),
              ),
            const SizedBox(height: 4),
            Text(
              '${item.dateLabel} · ${item.daysUntil}天后',
              style: const TextStyle(
                fontSize: 13,
                color: AppColors.textTertiary,
              ),
            ),
            const SizedBox(height: 16),
          ],
        ),
      ),
    );
  }
}
