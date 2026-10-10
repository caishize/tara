import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:equatable/equatable.dart';
import '../../../relationships/data/datasources/relationship_remote_datasource.dart';
import '../pages/dashboard_page.dart';

// Events
abstract class DashboardEvent extends Equatable {
  const DashboardEvent();

  @override
  List<Object?> get props => [];
}

class LoadDashboardData extends DashboardEvent {
  const LoadDashboardData();
}

class RefreshDashboardData extends DashboardEvent {
  const RefreshDashboardData();
}

class LoadWeatherData extends DashboardEvent {
  final double? latitude;
  final double? longitude;

  const LoadWeatherData({this.latitude, this.longitude});

  @override
  List<Object?> get props => [latitude, longitude];
}

class LoadRelationshipHealth extends DashboardEvent {
  const LoadRelationshipHealth();
}

// States
abstract class DashboardState extends Equatable {
  const DashboardState();

  @override
  List<Object?> get props => [];
}

class DashboardInitial extends DashboardState {
  const DashboardInitial();
}

class DashboardLoading extends DashboardState {
  const DashboardLoading();
}

class DashboardLoaded extends DashboardState {
  final WeatherInfo? weather;
  final List<RelationshipHealthData> relationshipHealth;
  final DateTime lastUpdated;

  const DashboardLoaded({
    this.weather,
    this.relationshipHealth = const [],
    required this.lastUpdated,
  });

  @override
  List<Object?> get props => [weather, relationshipHealth, lastUpdated];

  DashboardLoaded copyWith({
    WeatherInfo? weather,
    List<RelationshipHealthData>? relationshipHealth,
    DateTime? lastUpdated,
  }) {
    return DashboardLoaded(
      weather: weather ?? this.weather,
      relationshipHealth: relationshipHealth ?? this.relationshipHealth,
      lastUpdated: lastUpdated ?? this.lastUpdated,
    );
  }
}

class DashboardError extends DashboardState {
  final String message;

  const DashboardError(this.message);

  @override
  List<Object?> get props => [message];
}

// Bloc
class DashboardBloc extends Bloc<DashboardEvent, DashboardState> {
  final RelationshipRemoteDataSource? _relationshipDataSource;

  DashboardBloc({
    RelationshipRemoteDataSource? relationshipDataSource,
  })  : _relationshipDataSource = relationshipDataSource,
        super(const DashboardInitial()) {
    on<LoadDashboardData>(_onLoadDashboardData);
    on<RefreshDashboardData>(_onRefreshDashboardData);
    on<LoadWeatherData>(_onLoadWeatherData);
    on<LoadRelationshipHealth>(_onLoadRelationshipHealth);
  }

  Future<void> _onLoadDashboardData(
    LoadDashboardData event,
    Emitter<DashboardState> emit,
  ) async {
    emit(const DashboardLoading());

    try {
      // Load weather and relationship health in parallel
      final results = await Future.wait([
        _fetchWeather(),
        _fetchRelationshipHealth(),
      ]);

      emit(DashboardLoaded(
        weather: results[0] as WeatherInfo?,
        relationshipHealth: results[1] as List<RelationshipHealthData>,
        lastUpdated: DateTime.now(),
      ));
    } catch (e) {
      emit(DashboardError(e.toString()));
    }
  }

  Future<void> _onRefreshDashboardData(
    RefreshDashboardData event,
    Emitter<DashboardState> emit,
  ) async {
    // Keep current state while refreshing
    final currentState = state;

    try {
      final results = await Future.wait([
        _fetchWeather(),
        _fetchRelationshipHealth(),
      ]);

      emit(DashboardLoaded(
        weather: results[0] as WeatherInfo?,
        relationshipHealth: results[1] as List<RelationshipHealthData>,
        lastUpdated: DateTime.now(),
      ));
    } catch (e) {
      // On error, keep previous state if available
      if (currentState is DashboardLoaded) {
        emit(currentState);
      } else {
        emit(DashboardError(e.toString()));
      }
    }
  }

  Future<void> _onLoadWeatherData(
    LoadWeatherData event,
    Emitter<DashboardState> emit,
  ) async {
    final currentState = state;
    if (currentState is DashboardLoaded) {
      try {
        final weather = await _fetchWeather(
          latitude: event.latitude,
          longitude: event.longitude,
        );
        emit(currentState.copyWith(weather: weather));
      } catch (_) {
        // Keep current state on error
      }
    }
  }

  Future<void> _onLoadRelationshipHealth(
    LoadRelationshipHealth event,
    Emitter<DashboardState> emit,
  ) async {
    final currentState = state;
    if (currentState is DashboardLoaded) {
      try {
        final health = await _fetchRelationshipHealth();
        emit(currentState.copyWith(relationshipHealth: health));
      } catch (_) {
        // Keep current state on error
      }
    }
  }

  Future<WeatherInfo?> _fetchWeather({
    double? latitude,
    double? longitude,
  }) async {
    // Weather API not implemented yet - return null (no hardcoded data)
    // TODO: Implement weather API integration when available
    return null;
  }

  Future<List<RelationshipHealthData>> _fetchRelationshipHealth() async {
    if (_relationshipDataSource == null) {
      return const [];
    }

    try {
      // Get members that need attention from real API
      final members = await _relationshipDataSource.getAttentionNeeded(limit: 5);

      return members.map((m) => RelationshipHealthData(
        memberId: m.id,
        name: m.nickname ?? m.name,
        relationType: m.relationType,
        healthScore: m.score.total.toInt(),
        suggestion: m.suggestedActions.isNotEmpty
            ? m.suggestedActions.first.description
            : '保持联系',
        avatarUrl: m.avatarUrl,
        daysSinceContact: m.score.daysSinceContact,
      )).toList();
    } catch (e) {
      // Return empty list on error (no hardcoded fallback)
      return const [];
    }
  }
}
