import '../../domain/entities/poi.dart';
import '../../domain/entities/poi_category.dart';
import '../../domain/entities/secretary_recommendation.dart';
import '../../domain/repositories/guardian_repository.dart';
import '../datasources/guardian_remote_datasource.dart';

/// Guardian repository implementation
class GuardianRepositoryImpl implements GuardianRepository {
  final GuardianRemoteDataSource _dataSource;

  GuardianRepositoryImpl({required GuardianRemoteDataSource dataSource})
      : _dataSource = dataSource;

  @override
  Future<List<POI>> getPOIs({
    String? tripId,
    String? destination,
    POICategory? category,
    String? query,
  }) async {
    return _dataSource.getPOIs(
      tripId: tripId,
      destination: destination,
      category: category,
      query: query,
    );
  }

  @override
  Future<POI> getPOIDetail(String poiId) async {
    return _dataSource.getPOIDetail(poiId);
  }

  @override
  Future<List<SecretaryRecommendation>> getRecommendations({
    String? tripId,
    String? destination,
  }) async {
    return _dataSource.getRecommendations(
      tripId: tripId,
      destination: destination,
    );
  }

  @override
  Future<GuardianTripPlan> getTripPlan(String tripId) async {
    final data = await _dataSource.getTripPlan(tripId);
    return GuardianTripPlan(
      tripId: data['id'] as String? ?? tripId,
      tripName: data['trip_name'] as String? ?? data['destination'] as String? ?? '',
      destination: data['destination'] as String? ?? '',
      startDate: DateTime.parse(data['start_date'] as String),
      endDate: DateTime.parse(data['end_date'] as String),
    );
  }

  @override
  Future<List<GuardianDayItinerary>> getTripItinerary(String tripId) async {
    final items = await _dataSource.getTripItinerary(tripId);
    final tripPlan = await getTripPlan(tripId);

    return items.map((item) {
      final dayNumber = item['day_number'] as int;
      final activities = (item['activities'] as List<dynamic>? ?? [])
          .map((a) => _parseActivity(a as Map<String, dynamic>))
          .toList();

      return GuardianDayItinerary(
        dayNumber: dayNumber,
        date: tripPlan.startDate.add(Duration(days: dayNumber - 1)),
        activities: activities,
        secretaryAdvice: item['secretary_advice'] as String?,
      );
    }).toList();
  }

  GuardianActivity _parseActivity(Map<String, dynamic> data) {
    return GuardianActivity(
      id: data['id'] as String? ?? '',
      title: data['title'] as String? ?? '',
      subtitle: data['description'] as String? ?? data['activity_type'] as String?,
      time: data['time'] as String? ?? '',
      status: data['booking_info'] as String?,
      location: data['location'] as String?,
    );
  }

  @override
  Future<void> addPOIToItinerary({
    required String tripId,
    required String poiId,
    required int dayNumber,
  }) async {
    return _dataSource.addPOIToItinerary(
      tripId: tripId,
      poiId: poiId,
      dayNumber: dayNumber,
    );
  }

  @override
  Future<void> toggleFavorite(String poiId) async {
    return _dataSource.toggleFavorite(poiId);
  }
}
