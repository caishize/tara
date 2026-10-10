import '../../../../core/network/api_client.dart';
import '../../domain/entities/poi_category.dart';
import '../models/poi_model.dart';
import '../models/secretary_recommendation_model.dart';

/// Guardian remote data source
class GuardianRemoteDataSource {
  final ApiClient _apiClient;

  GuardianRemoteDataSource({required ApiClient apiClient})
      : _apiClient = apiClient;

  /// Get POIs from server
  Future<List<POIModel>> getPOIs({
    String? tripId,
    String? destination,
    POICategory? category,
    String? query,
  }) async {
    final queryParams = <String, dynamic>{};
    if (tripId != null) queryParams['trip_id'] = tripId;
    if (destination != null) queryParams['destination'] = destination;
    if (category != null) queryParams['category'] = category.name;
    if (query != null && query.isNotEmpty) queryParams['query'] = query;

    final response = await _apiClient.get(
      '/guardian/pois',
      queryParameters: queryParams,
    );
    final items = response['items'] as List<dynamic>? ?? [];
    return items
        .map((e) => POIModel.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  /// Get POI detail
  Future<POIModel> getPOIDetail(String poiId) async {
    final response = await _apiClient.get('/guardian/pois/$poiId');
    return POIModel.fromJson(response);
  }

  /// Get secretary recommendations
  Future<List<SecretaryRecommendationModel>> getRecommendations({
    String? tripId,
    String? destination,
  }) async {
    final queryParams = <String, dynamic>{};
    if (tripId != null) queryParams['trip_id'] = tripId;
    if (destination != null) queryParams['destination'] = destination;

    final response = await _apiClient.get(
      '/guardian/recommendations',
      queryParameters: queryParams,
    );
    final items = response['items'] as List<dynamic>? ?? [];
    return items
        .map((e) => SecretaryRecommendationModel.fromJson(
            e as Map<String, dynamic>))
        .toList();
  }

  /// Get trip plan details
  Future<Map<String, dynamic>> getTripPlan(String tripId) async {
    final response = await _apiClient.get('/travel/plans/$tripId');
    return response;
  }

  /// Get trip itinerary
  Future<List<Map<String, dynamic>>> getTripItinerary(String tripId) async {
    final response = await _apiClient.get('/travel/plans/$tripId/itinerary');
    final items = response['items'] as List<dynamic>? ?? [];
    return items.cast<Map<String, dynamic>>();
  }

  /// Add POI to itinerary
  Future<void> addPOIToItinerary({
    required String tripId,
    required String poiId,
    required int dayNumber,
  }) async {
    await _apiClient.post(
      '/guardian/itinerary/add',
      data: {
        'trip_id': tripId,
        'poi_id': poiId,
        'day_number': dayNumber,
      },
    );
  }

  /// Toggle favorite status
  Future<void> toggleFavorite(String poiId) async {
    await _apiClient.post('/guardian/pois/$poiId/favorite');
  }
}
