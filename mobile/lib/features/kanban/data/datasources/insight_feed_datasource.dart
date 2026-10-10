import '../../../../core/network/api_client.dart';
import '../models/future_view_models.dart';
import '../models/insight_feed_models.dart';

/// Abstract interface for insight feed remote data source.
///
/// Extracted from [CuratedTimelineRemoteDataSource] to give the insight feed
/// its own data layer, matching the BLoC-level separation already in place.
abstract class InsightFeedRemoteDataSource {
  /// Fetch insight-centric feed with optional cursor-based pagination.
  Future<InsightFeedResponseModel> fetchInsightFeed({
    int limit,
    String? cursor,
  });

  /// Execute an insight action by creating a PendingAction.
  Future<PendingActionResponseModel> executeInsightAction({
    required String insightId,
    required String actionType,
    Map<String, dynamic>? actionData,
  });

  /// Confirm and execute a pending action.
  Future<void> confirmAction({required String actionId});

  /// Submit insight feedback (useful/not_useful/dismiss/defer/never/acknowledged).
  Future<void> submitInsightFeedback({
    required String insightId,
    required String feedbackType,
    String? reason,
  });

  /// Adopt an insight to a trip (status → acted, creates trip entity link).
  Future<void> adoptInsight({
    required String insightId,
    required String tripId,
  });

  /// Fetch the future view (trips, suggestions, upcoming, family).
  Future<FutureViewResponseModel> fetchFutureView();

  /// Fetch more upcoming items (lazy loading).
  Future<FutureViewUpcomingPageModel> fetchMoreUpcoming({
    required int offset,
    int limit = 10,
  });

  /// Accept an AI suggestion sub-item → add as trip preparation item.
  Future<void> acceptSuggestionToTrip({
    required String tripId,
    required String itemText,
    String? insightId,
  });

  /// Toggle a trip preparation item's done status.
  Future<void> togglePreparationItem({
    required String tripId,
    required String taskId,
    required bool done,
  });

  /// Fetch structured insights for a specific trip.
  Future<List<InsightFeedItemModel>> fetchTripInsights({
    required String tripId,
  });
}

/// Implementation of [InsightFeedRemoteDataSource].
class InsightFeedRemoteDataSourceImpl implements InsightFeedRemoteDataSource {
  final ApiClient apiClient;

  InsightFeedRemoteDataSourceImpl({required this.apiClient});

  @override
  Future<InsightFeedResponseModel> fetchInsightFeed({
    int limit = 20,
    String? cursor,
  }) async {
    try {
      final queryParams = <String, String>{
        'limit': limit.toString(),
        'format': 'grouped',
      };
      if (cursor != null) {
        queryParams['cursor'] = cursor;
      }
      final response = await apiClient.get<Map<String, dynamic>>(
        '/kanban/insight-feed',
        queryParameters: queryParams,
      );
      return InsightFeedResponseModel.fromJson(response);
    } catch (e) {
      rethrow;
    }
  }

  @override
  Future<PendingActionResponseModel> executeInsightAction({
    required String insightId,
    required String actionType,
    Map<String, dynamic>? actionData,
  }) async {
    final response = await apiClient.post<Map<String, dynamic>>(
      '/actions/from-insight',
      data: {
        'insight_id': insightId,
        'action_type': actionType,
        if (actionData != null) 'action_data': actionData,
      },
    );
    return PendingActionResponseModel.fromJson(response);
  }

  @override
  Future<void> confirmAction({required String actionId}) async {
    await apiClient.post<Map<String, dynamic>>(
      '/actions/$actionId/confirm',
      data: {'execute_immediately': true},
    );
  }

  @override
  Future<void> submitInsightFeedback({
    required String insightId,
    required String feedbackType,
    String? reason,
  }) async {
    await apiClient.post<Map<String, dynamic>>(
      '/insights/$insightId/feedback',
      data: {
        'feedback': feedbackType,
        if (reason != null) 'reason': reason,
      },
    );
  }

  @override
  Future<void> adoptInsight({
    required String insightId,
    required String tripId,
  }) async {
    await apiClient.post<Map<String, dynamic>>(
      '/insights/$insightId/adopt',
      data: {'trip_id': tripId},
    );
  }

  @override
  Future<FutureViewResponseModel> fetchFutureView() async {
    try {
      final response = await apiClient.get<Map<String, dynamic>>(
        '/kanban/future-view',
      );
      return FutureViewResponseModel.fromJson(response);
    } catch (e) {
      rethrow;
    }
  }

  @override
  Future<FutureViewUpcomingPageModel> fetchMoreUpcoming({
    required int offset,
    int limit = 10,
  }) async {
    final response = await apiClient.get<Map<String, dynamic>>(
      '/kanban/future-view/upcoming',
      queryParameters: {
        'offset': offset.toString(),
        'limit': limit.toString(),
      },
    );
    return FutureViewUpcomingPageModel.fromJson(response);
  }

  @override
  Future<void> acceptSuggestionToTrip({
    required String tripId,
    required String itemText,
    String? insightId,
  }) async {
    await apiClient.post<Map<String, dynamic>>(
      '/kanban/future-view/accept-suggestion',
      data: {
        'trip_id': tripId,
        'item_text': itemText,
        if (insightId != null && insightId.isNotEmpty) 'insight_id': insightId,
      },
    );
  }

  @override
  Future<void> togglePreparationItem({
    required String tripId,
    required String taskId,
    required bool done,
  }) async {
    await apiClient.patch<Map<String, dynamic>>(
      '/kanban/trips/$tripId/preparation',
      data: {
        'item_key': taskId,
        'done': done,
      },
    );
  }

  @override
  Future<List<InsightFeedItemModel>> fetchTripInsights({
    required String tripId,
  }) async {
    try {
      final response = await apiClient.get<Map<String, dynamic>>(
        '/insights/for-trip/$tripId',
      );
      final rawInsights = response['insights'] as List<dynamic>?;
      if (rawInsights == null) return const [];
      return rawInsights
          .map((e) =>
              InsightFeedItemModel.fromJson(e as Map<String, dynamic>))
          .toList();
    } catch (e) {
      rethrow;
    }
  }
}
