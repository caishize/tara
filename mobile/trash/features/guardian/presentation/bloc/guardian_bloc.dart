import 'package:flutter_bloc/flutter_bloc.dart';
import '../../domain/entities/poi.dart';
import '../../domain/entities/secretary_recommendation.dart';
import '../../domain/repositories/guardian_repository.dart';
import 'guardian_event.dart';
import 'guardian_state.dart';

/// Guardian BLoC for managing exploration and trip planning
class GuardianBloc extends Bloc<GuardianEvent, GuardianState> {
  final GuardianRepository _repository;
  String? _currentTripId;
  String? _currentDestination;

  GuardianBloc({required GuardianRepository repository})
      : _repository = repository,
        super(const GuardianInitial()) {
    on<GuardianLoadRequested>(_onLoadRequested);
    on<POICategoryFilterChanged>(_onCategoryFilterChanged);
    on<POISearchRequested>(_onSearchRequested);
    on<POIDetailLoadRequested>(_onPOIDetailLoadRequested);
    on<TripPlanningLoadRequested>(_onTripPlanningLoadRequested);
    on<AddPOIToItinerary>(_onAddPOIToItinerary);
    on<TogglePOIFavorite>(_onToggleFavorite);
    on<GuardianRefreshRequested>(_onRefreshRequested);
  }

  Future<void> _onLoadRequested(
    GuardianLoadRequested event,
    Emitter<GuardianState> emit,
  ) async {
    emit(const GuardianLoading());
    _currentTripId = event.tripId;
    _currentDestination = event.destination;

    try {
      final results = await Future.wait([
        _repository.getPOIs(
          tripId: event.tripId,
          destination: event.destination,
        ),
        _repository.getRecommendations(
          tripId: event.tripId,
          destination: event.destination,
        ),
      ]);

      final pois = results[0];
      final recommendations = results[1];
      emit(TripExplorationLoaded(
        pois: pois is List<POI> ? pois : [],
        recommendations: recommendations is List<SecretaryRecommendation>
            ? recommendations
            : [],
        destination: event.destination,
      ));
    } catch (e) {
      emit(GuardianError('加载失败: $e'));
    }
  }

  void _onCategoryFilterChanged(
    POICategoryFilterChanged event,
    Emitter<GuardianState> emit,
  ) {
    final currentState = state;
    if (currentState is TripExplorationLoaded) {
      // Toggle off if same category selected
      final newCategory = currentState.selectedCategory == event.category
          ? null
          : event.category;
      emit(currentState.copyWith(
        selectedCategory: newCategory,
        clearCategory: newCategory == null,
      ));
    }
  }

  void _onSearchRequested(
    POISearchRequested event,
    Emitter<GuardianState> emit,
  ) {
    final currentState = state;
    if (currentState is TripExplorationLoaded) {
      emit(currentState.copyWith(
        searchQuery: event.query,
        clearSearchQuery: event.query.isEmpty,
      ));
    }
  }

  Future<void> _onPOIDetailLoadRequested(
    POIDetailLoadRequested event,
    Emitter<GuardianState> emit,
  ) async {
    emit(const GuardianLoading());

    try {
      final poi = await _repository.getPOIDetail(event.poiId);
      emit(POIDetailLoaded(poi: poi));
    } catch (e) {
      emit(GuardianError('加载详情失败: $e'));
    }
  }

  Future<void> _onTripPlanningLoadRequested(
    TripPlanningLoadRequested event,
    Emitter<GuardianState> emit,
  ) async {
    emit(const GuardianLoading());

    try {
      final tripPlan = await _repository.getTripPlan(event.tripId);
      final itinerary = await _repository.getTripItinerary(event.tripId);

      emit(TripPlanningLoaded(
        tripId: tripPlan.tripId,
        tripName: tripPlan.tripName,
        startDate: tripPlan.startDate,
        endDate: tripPlan.endDate,
        itinerary: itinerary,
      ));
    } catch (e) {
      emit(GuardianError('加载行程失败: $e'));
    }
  }

  Future<void> _onAddPOIToItinerary(
    AddPOIToItinerary event,
    Emitter<GuardianState> emit,
  ) async {
    try {
      await _repository.addPOIToItinerary(
        tripId: event.tripId,
        poiId: event.poiId,
        dayNumber: event.dayNumber,
      );
      // Reload trip planning data
      add(TripPlanningLoadRequested(event.tripId));
    } catch (e) {
      emit(GuardianError('添加到行程失败: $e'));
    }
  }

  Future<void> _onToggleFavorite(
    TogglePOIFavorite event,
    Emitter<GuardianState> emit,
  ) async {
    final currentState = state;
    if (currentState is POIDetailLoaded) {
      // Optimistic update
      emit(currentState.copyWith(isFavorite: !currentState.isFavorite));

      try {
        await _repository.toggleFavorite(event.poiId);
      } catch (e) {
        // Revert on error
        emit(currentState);
      }
    }
  }

  Future<void> _onRefreshRequested(
    GuardianRefreshRequested event,
    Emitter<GuardianState> emit,
  ) async {
    add(GuardianLoadRequested(
      tripId: _currentTripId,
      destination: _currentDestination,
    ));
  }
}
