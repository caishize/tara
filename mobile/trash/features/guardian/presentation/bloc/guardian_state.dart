import 'package:equatable/equatable.dart';
import '../../domain/entities/poi.dart';
import '../../domain/entities/poi_category.dart';
import '../../domain/entities/secretary_recommendation.dart';
import '../../domain/repositories/guardian_repository.dart';

/// Guardian BLoC states
abstract class GuardianState extends Equatable {
  const GuardianState();

  @override
  List<Object?> get props => [];
}

/// Initial state
class GuardianInitial extends GuardianState {
  const GuardianInitial();
}

/// Loading state
class GuardianLoading extends GuardianState {
  const GuardianLoading();
}

/// Trip exploration loaded state
class TripExplorationLoaded extends GuardianState {
  final List<POI> pois;
  final List<SecretaryRecommendation> recommendations;
  final POICategory? selectedCategory;
  final String? searchQuery;
  final String? destination;

  const TripExplorationLoaded({
    required this.pois,
    required this.recommendations,
    this.selectedCategory,
    this.searchQuery,
    this.destination,
  });

  /// Get filtered POIs based on category and search
  List<POI> get filteredPOIs {
    var result = pois;

    if (selectedCategory != null) {
      result = result.where((p) => p.category == selectedCategory).toList();
    }

    if (searchQuery != null && searchQuery!.isNotEmpty) {
      final query = searchQuery!.toLowerCase();
      result = result
          .where((p) =>
              p.name.toLowerCase().contains(query) ||
              p.address.toLowerCase().contains(query) ||
              p.tags.any((tag) => tag.toLowerCase().contains(query)))
          .toList();
    }

    return result;
  }

  TripExplorationLoaded copyWith({
    List<POI>? pois,
    List<SecretaryRecommendation>? recommendations,
    POICategory? selectedCategory,
    String? searchQuery,
    String? destination,
    bool clearCategory = false,
    bool clearSearchQuery = false,
  }) {
    return TripExplorationLoaded(
      pois: pois ?? this.pois,
      recommendations: recommendations ?? this.recommendations,
      selectedCategory:
          clearCategory ? null : (selectedCategory ?? this.selectedCategory),
      searchQuery:
          clearSearchQuery ? null : (searchQuery ?? this.searchQuery),
      destination: destination ?? this.destination,
    );
  }

  @override
  List<Object?> get props => [
        pois,
        recommendations,
        selectedCategory,
        searchQuery,
        destination,
      ];
}

/// POI detail loaded state
class POIDetailLoaded extends GuardianState {
  final POI poi;
  final bool isFavorite;

  const POIDetailLoaded({
    required this.poi,
    this.isFavorite = false,
  });

  POIDetailLoaded copyWith({
    POI? poi,
    bool? isFavorite,
  }) {
    return POIDetailLoaded(
      poi: poi ?? this.poi,
      isFavorite: isFavorite ?? this.isFavorite,
    );
  }

  @override
  List<Object?> get props => [poi, isFavorite];
}

/// Trip planning loaded state
class TripPlanningLoaded extends GuardianState {
  final String tripId;
  final String tripName;
  final DateTime startDate;
  final DateTime endDate;
  final List<GuardianDayItinerary> itinerary;
  final int selectedDay;

  const TripPlanningLoaded({
    required this.tripId,
    required this.tripName,
    required this.startDate,
    required this.endDate,
    required this.itinerary,
    this.selectedDay = 1,
  });

  int get totalDays => endDate.difference(startDate).inDays + 1;

  GuardianDayItinerary? get currentDayItinerary {
    if (selectedDay <= 0 || selectedDay > itinerary.length) return null;
    return itinerary[selectedDay - 1];
  }

  TripPlanningLoaded copyWith({
    String? tripId,
    String? tripName,
    DateTime? startDate,
    DateTime? endDate,
    List<GuardianDayItinerary>? itinerary,
    int? selectedDay,
  }) {
    return TripPlanningLoaded(
      tripId: tripId ?? this.tripId,
      tripName: tripName ?? this.tripName,
      startDate: startDate ?? this.startDate,
      endDate: endDate ?? this.endDate,
      itinerary: itinerary ?? this.itinerary,
      selectedDay: selectedDay ?? this.selectedDay,
    );
  }

  @override
  List<Object?> get props =>
      [tripId, tripName, startDate, endDate, itinerary, selectedDay];
}

/// Error state
class GuardianError extends GuardianState {
  final String message;

  const GuardianError(this.message);

  @override
  List<Object?> get props => [message];
}
