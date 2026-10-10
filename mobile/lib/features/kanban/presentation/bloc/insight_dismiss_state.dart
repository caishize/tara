import 'package:equatable/equatable.dart';

import '../../data/models/insight_feed_models.dart';

/// Tracks an insight that was dismissed but not yet committed to the backend.
///
/// Used by the undo-dismiss flow: insight stays in [recentlyDismissed] for
/// a grace period (4s) during which the user can tap "撤销" to restore it.
class DismissedInsightEntry extends Equatable {
  final InsightFeedItemModel insight;
  final DateTime dismissedAt;

  /// Original index in the flat feed list, used to restore position on undo.
  final int originalIndex;

  /// The groupId the insight belonged to (if grouped feed), for positional restore.
  final String? groupId;

  /// PLAN-003: Feedback type for analytics (e.g. 'dismiss', 'ignore').
  final String feedbackType;

  const DismissedInsightEntry({
    required this.insight,
    required this.dismissedAt,
    required this.originalIndex,
    this.groupId,
    this.feedbackType = 'dismiss',
  });

  @override
  List<Object?> get props => [insight.id, dismissedAt, originalIndex, groupId, feedbackType];
}

/// States for the dedicated dismiss-with-undo lifecycle BLoC.
sealed class InsightDismissState extends Equatable {
  const InsightDismissState();

  /// Convenience accessor for recently dismissed entries.
  List<DismissedInsightEntry> get recentlyDismissed => const [];

  @override
  List<Object?> get props => [];
}

/// No pending dismisses.
class InsightDismissIdle extends InsightDismissState {
  const InsightDismissIdle();
}

/// One or more insights are pending dismiss (undo window active).
class InsightDismissActive extends InsightDismissState {
  @override
  final List<DismissedInsightEntry> recentlyDismissed;

  const InsightDismissActive({
    required this.recentlyDismissed,
  });

  @override
  List<Object?> get props => [recentlyDismissed];
}
