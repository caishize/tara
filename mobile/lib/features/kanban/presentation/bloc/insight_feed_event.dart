import 'package:equatable/equatable.dart';

import '../../data/models/insight_feed_models.dart';

/// Insight feed events — dedicated to feed data lifecycle.
///
/// PLAN-001: Dismiss events moved to [InsightDismissEvent].
/// Action events moved to [ActionEvent].
sealed class InsightFeedEvent extends Equatable {
  const InsightFeedEvent();

  @override
  List<Object?> get props => [];
}

/// Load the insight-centric feed from scratch
class LoadInsightFeed extends InsightFeedEvent {
  const LoadInsightFeed();
}

/// Refresh the insight-centric feed (pull-to-refresh)
class RefreshInsightFeed extends InsightFeedEvent {
  const RefreshInsightFeed();
}

/// Load the next page of insights (cursor comes from current state)
class LoadMoreInsightFeed extends InsightFeedEvent {
  const LoadMoreInsightFeed();
}

/// Expand a single insight card (accordion — only one open at a time)
class ExpandInsight extends InsightFeedEvent {
  final String insightId;

  const ExpandInsight(this.insightId);

  @override
  List<Object?> get props => [insightId];
}

/// Collapse the currently expanded insight card
class CollapseInsight extends InsightFeedEvent {
  const CollapseInsight();
}

/// Submit insight feedback — combines MarkInsightUseful + DismissInsight
/// semantics for the feed context (positive feedback with delayed removal,
/// or negative/dismiss feedback with immediate removal).
class SubmitInsightFeedback extends InsightFeedEvent {
  final String insightId;
  final String feedbackType; // 'useful', 'not_useful', 'dismiss', 'defer', 'never'

  const SubmitInsightFeedback({
    required this.insightId,
    required this.feedbackType,
  });

  @override
  List<Object?> get props => [insightId, feedbackType];
}

// ---------------------------------------------------------------------------
// Group expand events
// ---------------------------------------------------------------------------

/// Toggle a semantic group's expand/collapse state.
class ToggleGroupExpand extends InsightFeedEvent {
  final String groupId;

  const ToggleGroupExpand(this.groupId);

  @override
  List<Object?> get props => [groupId];
}

/// Set whether the flat-feed "later" section is fully expanded.
class SetShowAllLaterInsights extends InsightFeedEvent {
  final bool show;

  const SetShowAllLaterInsights(this.show);

  @override
  List<Object?> get props => [show];
}

/// Apply server-driven default group expansion (called once after first load).
class ApplyDefaultGroupExpansion extends InsightFeedEvent {
  final List<String> groupIds;

  const ApplyDefaultGroupExpansion(this.groupIds);

  @override
  List<Object?> get props => [groupIds];
}

// ---------------------------------------------------------------------------
// Feed mutation events (driven by dismiss/action blocs via page coordinator)
// ---------------------------------------------------------------------------

/// Remove an insight from the feed (optimistic, from dismiss BLoC).
class RemoveInsightFromFeed extends InsightFeedEvent {
  final String insightId;

  const RemoveInsightFromFeed(this.insightId);

  @override
  List<Object?> get props => [insightId];
}

/// Restore a dismissed insight to the feed (undo).
class RestoreInsightToFeed extends InsightFeedEvent {
  final InsightFeedItemModel insight;
  final int originalIndex;
  final String? groupId;

  const RestoreInsightToFeed({
    required this.insight,
    required this.originalIndex,
    this.groupId,
  });

  @override
  List<Object?> get props => [insight.id, originalIndex, groupId];
}

/// Mark an insight as adopted (visual change after action confirmed).
class MarkInsightAdopted extends InsightFeedEvent {
  final String insightId;

  const MarkInsightAdopted(this.insightId);

  @override
  List<Object?> get props => [insightId];
}
