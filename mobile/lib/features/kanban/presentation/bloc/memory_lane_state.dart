import 'package:equatable/equatable.dart';
import '../../data/models/insight_feed_models.dart';
import '../../domain/entities/memory_lane.dart';

/// Memory lane states
abstract class MemoryLaneState extends Equatable {
  const MemoryLaneState();

  @override
  List<Object?> get props => [];
}

/// Initial state
class MemoryLaneInitial extends MemoryLaneState {
  const MemoryLaneInitial();
}

/// Loading state
class MemoryLaneLoading extends MemoryLaneState {
  const MemoryLaneLoading();
}

/// Memory lane loaded state
class MemoryLaneLoaded extends MemoryLaneState {
  final List<OnThisDayItem> onThisDayItems;
  final List<StoryGroup> recentStories;
  final List<YearlySummary> yearlySummaries;
  final Set<String> dismissedOnThisDayIds;
  final Set<int> expandedYears;
  final bool isRefreshing;

  /// PLAN-011: AI-generated memory reflection highlights.
  final List<InsightFeedItemModel> memoryHighlights;

  const MemoryLaneLoaded({
    this.onThisDayItems = const [],
    this.recentStories = const [],
    this.yearlySummaries = const [],
    this.dismissedOnThisDayIds = const {},
    this.expandedYears = const {},
    this.isRefreshing = false,
    this.memoryHighlights = const [],
  });

  List<OnThisDayItem> get visibleOnThisDayItems => onThisDayItems
      .where((item) => !dismissedOnThisDayIds.contains(item.id))
      .toList();

  MemoryLaneLoaded copyWith({
    List<OnThisDayItem>? onThisDayItems,
    List<StoryGroup>? recentStories,
    List<YearlySummary>? yearlySummaries,
    Set<String>? dismissedOnThisDayIds,
    Set<int>? expandedYears,
    bool? isRefreshing,
    List<InsightFeedItemModel>? memoryHighlights,
  }) {
    return MemoryLaneLoaded(
      onThisDayItems: onThisDayItems ?? this.onThisDayItems,
      recentStories: recentStories ?? this.recentStories,
      yearlySummaries: yearlySummaries ?? this.yearlySummaries,
      dismissedOnThisDayIds:
          dismissedOnThisDayIds ?? this.dismissedOnThisDayIds,
      expandedYears: expandedYears ?? this.expandedYears,
      isRefreshing: isRefreshing ?? this.isRefreshing,
      memoryHighlights: memoryHighlights ?? this.memoryHighlights,
    );
  }

  @override
  List<Object?> get props => [
        onThisDayItems,
        recentStories,
        yearlySummaries,
        dismissedOnThisDayIds,
        expandedYears,
        isRefreshing,
        memoryHighlights,
      ];
}

/// Error state
class MemoryLaneError extends MemoryLaneState {
  final String message;

  const MemoryLaneError({required this.message});

  @override
  List<Object?> get props => [message];
}
