import 'package:equatable/equatable.dart';
import '../../domain/entities/poi_category.dart';

/// Guardian BLoC events
abstract class GuardianEvent extends Equatable {
  const GuardianEvent();

  @override
  List<Object?> get props => [];
}

/// Load exploration data
class GuardianLoadRequested extends GuardianEvent {
  final String? tripId;
  final String? destination;

  const GuardianLoadRequested({this.tripId, this.destination});

  @override
  List<Object?> get props => [tripId, destination];
}

/// Filter POIs by category
class POICategoryFilterChanged extends GuardianEvent {
  final POICategory? category;

  const POICategoryFilterChanged(this.category);

  @override
  List<Object?> get props => [category];
}

/// Search for POIs
class POISearchRequested extends GuardianEvent {
  final String query;

  const POISearchRequested(this.query);

  @override
  List<Object?> get props => [query];
}

/// Load POI detail
class POIDetailLoadRequested extends GuardianEvent {
  final String poiId;

  const POIDetailLoadRequested(this.poiId);

  @override
  List<Object?> get props => [poiId];
}

/// Load trip planning data
class TripPlanningLoadRequested extends GuardianEvent {
  final String tripId;

  const TripPlanningLoadRequested(this.tripId);

  @override
  List<Object?> get props => [tripId];
}

/// Add POI to itinerary
class AddPOIToItinerary extends GuardianEvent {
  final String tripId;
  final String poiId;
  final int dayNumber;

  const AddPOIToItinerary({
    required this.tripId,
    required this.poiId,
    required this.dayNumber,
  });

  @override
  List<Object?> get props => [tripId, poiId, dayNumber];
}

/// Toggle favorite status
class TogglePOIFavorite extends GuardianEvent {
  final String poiId;

  const TogglePOIFavorite(this.poiId);

  @override
  List<Object?> get props => [poiId];
}

/// Refresh data
class GuardianRefreshRequested extends GuardianEvent {
  const GuardianRefreshRequested();
}
