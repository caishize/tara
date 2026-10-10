import 'package:equatable/equatable.dart';

import '../../data/models/insight_feed_models.dart';

/// Action lifecycle state for an individual insight action button.
///
/// Canonical location — all insight-related widgets import from here.
enum InsightActionState { idle, pending, pendingConfirm, confirmed, failed }

/// Insight feed states — dedicated state hierarchy for [InsightFeedBloc].
///
/// PLAN-001: Dismiss state moved to [InsightDismissState].
/// Action state moved to [ActionState].
sealed class InsightFeedState extends Equatable {
  const InsightFeedState();

  @override
  List<Object?> get props => [];
}

/// Initial state before any load has been triggered
class InsightFeedInitial extends InsightFeedState {
  const InsightFeedInitial();
}

/// Feed is loading (first load or full reload)
class InsightFeedLoadingState extends InsightFeedState {
  const InsightFeedLoadingState();
}

/// Feed has been loaded successfully
class InsightFeedLoadedState extends InsightFeedState {
  final InsightFeedResponseModel feed;
  final bool isRefreshing;
  final String? expandedInsightId;
  final Set<String> adoptedInsightIds;

  /// Opaque cursor for fetching the next page.
  final String? nextCursor;

  /// Whether the backend has more items beyond the current page.
  final bool hasMore;

  /// Whether a load-more request is currently in flight.
  final bool isLoadingMore;

  // -- Group expand state ---------------------------------------------------

  /// IDs of groups currently expanded in the grouped feed view.
  final Set<String> expandedGroupIds;

  /// Whether the flat-feed "later" section is fully expanded.
  final bool showAllLaterInsights;

  /// Whether server-driven default group expansion has been applied.
  final bool defaultGroupExpansionApplied;

  // -- Smart reload ---------------------------------------------------------

  /// Timestamp of the last successful feed load, for staleness checks.
  final DateTime? lastLoadedAt;

  const InsightFeedLoadedState({
    required this.feed,
    this.isRefreshing = false,
    this.expandedInsightId,
    this.adoptedInsightIds = const {},
    this.nextCursor,
    this.hasMore = false,
    this.isLoadingMore = false,
    this.expandedGroupIds = const {},
    this.showAllLaterInsights = false,
    this.defaultGroupExpansionApplied = false,
    this.lastLoadedAt,
  });

  // ---------------------------------------------------------------------------
  // PLAN-001: Canonical visible insights list + O(1) group lookup
  // ---------------------------------------------------------------------------

  /// Canonical list of all currently visible insights, regardless of feed format.
  ///
  /// If the feed uses grouped format, flattens all groups. Otherwise returns
  /// the flat insights list. NOT included in Equatable [props] — derived from
  /// [feed] which IS in props.
  List<InsightFeedItemModel> get allVisibleInsights {
    if (feed.groups.isNotEmpty) {
      return feed.groups.expand((g) => g.insights).toList();
    }
    return feed.insights;
  }

  /// Pre-computed map from insight ID to its group ID for O(1) lookup.
  ///
  /// Value is null for insights in the flat feed (no group). NOT included in
  /// Equatable [props] — derived from [feed] which IS in props.
  Map<String, String?> get insightIdToGroupId {
    final map = <String, String?>{};
    if (feed.groups.isNotEmpty) {
      for (final group in feed.groups) {
        for (final insight in group.insights) {
          map[insight.id] = group.groupId;
        }
      }
    } else {
      for (final insight in feed.insights) {
        map[insight.id] = null;
      }
    }
    return map;
  }

  InsightFeedLoadedState copyWith({
    InsightFeedResponseModel? feed,
    bool? isRefreshing,
    String? Function()? expandedInsightId,
    Set<String>? adoptedInsightIds,
    String? Function()? nextCursor,
    bool? hasMore,
    bool? isLoadingMore,
    Set<String>? expandedGroupIds,
    bool? showAllLaterInsights,
    bool? defaultGroupExpansionApplied,
    DateTime? Function()? lastLoadedAt,
  }) {
    return InsightFeedLoadedState(
      feed: feed ?? this.feed,
      isRefreshing: isRefreshing ?? this.isRefreshing,
      expandedInsightId: expandedInsightId != null
          ? expandedInsightId()
          : this.expandedInsightId,
      adoptedInsightIds: adoptedInsightIds ?? this.adoptedInsightIds,
      nextCursor: nextCursor != null ? nextCursor() : this.nextCursor,
      hasMore: hasMore ?? this.hasMore,
      isLoadingMore: isLoadingMore ?? this.isLoadingMore,
      expandedGroupIds: expandedGroupIds ?? this.expandedGroupIds,
      showAllLaterInsights: showAllLaterInsights ?? this.showAllLaterInsights,
      defaultGroupExpansionApplied:
          defaultGroupExpansionApplied ?? this.defaultGroupExpansionApplied,
      lastLoadedAt: lastLoadedAt != null
          ? lastLoadedAt()
          : this.lastLoadedAt,
    );
  }

  @override
  List<Object?> get props => [
        feed,
        isRefreshing,
        expandedInsightId,
        adoptedInsightIds,
        nextCursor,
        hasMore,
        isLoadingMore,
        expandedGroupIds,
        showAllLaterInsights,
        defaultGroupExpansionApplied,
        lastLoadedAt,
      ];
}

/// Feed failed to load
class InsightFeedErrorState extends InsightFeedState {
  final String message;

  const InsightFeedErrorState(this.message);

  @override
  List<Object?> get props => [message];
}
