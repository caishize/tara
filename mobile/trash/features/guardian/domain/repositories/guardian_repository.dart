import '../entities/poi.dart';
import '../entities/poi_category.dart';
import '../entities/secretary_recommendation.dart';

/// Trip plan data for Guardian module
class GuardianTripPlan {
  final String tripId;
  final String tripName;
  final String destination;
  final DateTime startDate;
  final DateTime endDate;

  const GuardianTripPlan({
    required this.tripId,
    required this.tripName,
    required this.destination,
    required this.startDate,
    required this.endDate,
  });
}

/// Day itinerary data for Guardian module
class GuardianDayItinerary {
  final int dayNumber;
  final DateTime date;
  final List<GuardianActivity> activities;
  final String? secretaryAdvice;

  const GuardianDayItinerary({
    required this.dayNumber,
    required this.date,
    required this.activities,
    this.secretaryAdvice,
  });
}

/// Activity data for Guardian module
class GuardianActivity {
  final String id;
  final String title;
  final String? subtitle;
  final String time;
  final String? status;
  final String? location;

  const GuardianActivity({
    required this.id,
    required this.title,
    this.subtitle,
    required this.time,
    this.status,
    this.location,
  });
}

/// Guardian repository interface
abstract class GuardianRepository {
  /// Get POIs for exploration
  /// [tripId] - Optional trip ID to get trip-specific POIs
  /// [destination] - Optional destination to filter POIs
  /// [category] - Optional category filter
  /// [query] - Optional search query
  Future<List<POI>> getPOIs({
    String? tripId,
    String? destination,
    POICategory? category,
    String? query,
  });

  /// Get POI detail by ID
  Future<POI> getPOIDetail(String poiId);

  /// Get secretary recommendations
  /// [tripId] - Optional trip ID to get trip-specific recommendations
  /// [destination] - Optional destination to get destination-specific recommendations
  Future<List<SecretaryRecommendation>> getRecommendations({
    String? tripId,
    String? destination,
  });

  /// Get trip plan details
  Future<GuardianTripPlan> getTripPlan(String tripId);

  /// Get trip itinerary
  Future<List<GuardianDayItinerary>> getTripItinerary(String tripId);

  /// Add POI to itinerary
  /// [tripId] - Trip ID
  /// [poiId] - POI ID to add
  /// [dayNumber] - Day number to add to
  Future<void> addPOIToItinerary({
    required String tripId,
    required String poiId,
    required int dayNumber,
  });

  /// Toggle favorite status for a POI
  Future<void> toggleFavorite(String poiId);
}
