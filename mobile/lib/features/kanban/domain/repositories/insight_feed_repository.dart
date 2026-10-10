import 'package:dartz/dartz.dart';
import '../../../../core/error/failures.dart';
import '../../data/models/future_view_models.dart';
import '../../data/models/insight_feed_models.dart';

/// Repository interface for the insight-centric feed.
///
/// Extracted from [CuratedTimelineRepository] to give [InsightFeedBloc]
/// its own dependency, decoupled from timeline/kanban/schedule concerns.
abstract class InsightFeedRepository {
  /// Fetch insight-centric feed with optional cursor-based pagination.
  Future<Either<Failure, InsightFeedResponseModel>> getInsightFeed({
    int limit = 20,
    String? cursor,
  });

  /// Fetch the future view (trips, suggestions, upcoming, family).
  Future<Either<Failure, FutureViewResponseModel>> getFutureView();

  /// Fetch more upcoming items (lazy loading).
  Future<Either<Failure, FutureViewUpcomingPageModel>> getMoreUpcoming({
    required int offset,
    int limit = 10,
  });

  /// Accept an AI suggestion sub-item → add as trip preparation item.
  Future<Either<Failure, void>> acceptSuggestionToTrip({
    required String tripId,
    required String itemText,
    String? insightId,
  });

  /// Execute an insight action by creating a PendingAction.
  Future<Either<Failure, PendingActionResponseModel>> executeInsightAction({
    required String insightId,
    required String actionType,
    Map<String, dynamic>? actionData,
  });

  /// Confirm and execute a pending action.
  Future<Either<Failure, void>> confirmAction({
    required String actionId,
  });

  /// Submit insight feedback (useful/not_useful/dismiss/defer/never/acknowledged).
  Future<Either<Failure, void>> submitInsightFeedback({
    required String insightId,
    required String feedbackType,
    String? reason,
  });

  /// Adopt an insight to a trip (status → acted, creates trip entity link).
  Future<Either<Failure, void>> adoptInsight({
    required String insightId,
    required String tripId,
  });

  /// Toggle a trip preparation item's done status.
  Future<Either<Failure, void>> togglePreparationItem({
    required String tripId,
    required String taskId,
    required bool done,
  });

  /// Fetch structured insights for a specific trip.
  Future<Either<Failure, List<InsightFeedItemModel>>> getTripInsights({
    required String tripId,
  });
}
