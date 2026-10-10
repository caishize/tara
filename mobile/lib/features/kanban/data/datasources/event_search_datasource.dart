import '../../../../core/network/api_client.dart';
import 'curated_timeline_datasource.dart' show EventSearchResponse;

/// Abstract interface for event search remote data source.
///
/// Extracted from [CuratedTimelineRemoteDataSource] for single-responsibility.
abstract class EventSearchRemoteDataSource {
  /// Search events by query string with optional type filtering.
  Future<EventSearchResponse> searchEvents({
    required String query,
    List<String>? eventTypes,
    int limit,
  });
}

/// Implementation of [EventSearchRemoteDataSource].
class EventSearchRemoteDataSourceImpl implements EventSearchRemoteDataSource {
  final ApiClient apiClient;

  EventSearchRemoteDataSourceImpl({required this.apiClient});

  @override
  Future<EventSearchResponse> searchEvents({
    required String query,
    List<String>? eventTypes,
    int limit = 20,
  }) async {
    final queryParams = <String, dynamic>{
      'q': query,
      'limit': limit.toString(),
    };
    if (eventTypes != null && eventTypes.isNotEmpty) {
      queryParams['event_types'] = eventTypes.join(',');
    }

    final response = await apiClient.get<Map<String, dynamic>>(
      '/kanban/events/search',
      queryParameters: queryParams,
    );

    return EventSearchResponse.fromJson(response);
  }
}
