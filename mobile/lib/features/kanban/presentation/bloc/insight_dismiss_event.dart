import 'package:equatable/equatable.dart';

import '../../data/models/insight_feed_models.dart';

/// Events for the dedicated dismiss-with-undo lifecycle BLoC.
///
/// Extracted from InsightFeedEvent (PLAN-001) to give dismiss logic
/// its own event hierarchy.
sealed class InsightDismissEvent extends Equatable {
  const InsightDismissEvent();

  @override
  List<Object?> get props => [];
}

/// Dismiss an insight with undo support.
///
/// Carries the full insight model and positional info so the dismiss
/// BLoC can store everything needed for undo restoration.
/// PLAN-003: [feedbackType] preserves analytics metadata (e.g. 'dismiss', 'ignore').
class DismissInsight extends InsightDismissEvent {
  final InsightFeedItemModel insight;
  final int originalIndex;
  final String? groupId;

  /// Optional feedback type for analytics. Defaults to 'dismiss'.
  final String feedbackType;

  const DismissInsight({
    required this.insight,
    required this.originalIndex,
    this.groupId,
    this.feedbackType = 'dismiss',
  });

  @override
  List<Object?> get props => [insight.id, originalIndex, groupId, feedbackType];
}

/// Undo a recent dismiss — restore the insight.
class UndoDismiss extends InsightDismissEvent {
  final String insightId;

  const UndoDismiss(this.insightId);

  @override
  List<Object?> get props => [insightId];
}

/// Commit a dismissed insight to the backend (timer expired).
class CommitDismiss extends InsightDismissEvent {
  final String insightId;

  const CommitDismiss(this.insightId);

  @override
  List<Object?> get props => [insightId];
}

/// Commit all pending dismisses (e.g. on app backgrounding).
class CommitAllDismisses extends InsightDismissEvent {
  const CommitAllDismisses();
}
