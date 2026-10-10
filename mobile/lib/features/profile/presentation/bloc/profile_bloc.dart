import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:equatable/equatable.dart';

import '../../data/datasources/profile_remote_datasource.dart';
import '../../domain/entities/activity_record.dart';
import '../../domain/entities/user_stats.dart';
import '../../domain/entities/smart_service.dart';
import '../../domain/repositories/profile_repository.dart';

// Events
abstract class ProfileEvent extends Equatable {
  const ProfileEvent();

  @override
  List<Object?> get props => [];
}

class ProfileLoadRequested extends ProfileEvent {
  const ProfileLoadRequested();
}

class ProfileRefreshRequested extends ProfileEvent {
  const ProfileRefreshRequested();
}

class SmartServiceToggled extends ProfileEvent {
  final String serviceId;
  final bool enable;

  const SmartServiceToggled({
    required this.serviceId,
    required this.enable,
  });

  @override
  List<Object?> get props => [serviceId, enable];
}

class SmartServiceTriggered extends ProfileEvent {
  final String serviceId;
  final String jobName;

  const SmartServiceTriggered({
    required this.serviceId,
    required this.jobName,
  });

  @override
  List<Object?> get props => [serviceId, jobName];
}

// States
abstract class ProfileState extends Equatable {
  const ProfileState();

  @override
  List<Object?> get props => [];
}

class ProfileInitial extends ProfileState {
  const ProfileInitial();
}

class ProfileLoading extends ProfileState {
  const ProfileLoading();
}

class ProfileLoaded extends ProfileState {
  final UserStats stats;
  final SmartServicesSummary services;
  final Map<String, int> memberCountsByType;
  final int connectionCount;
  final List<String> connectedProviderTypes;
  final int memoryCount;
  final String? latestInsight;
  final Map<String, dynamic> reportSummary;
  final ActivitySummary? activitySummary;

  const ProfileLoaded({
    required this.stats,
    required this.services,
    this.memberCountsByType = const {},
    this.connectionCount = 0,
    this.connectedProviderTypes = const [],
    this.memoryCount = 0,
    this.latestInsight,
    this.reportSummary = const {},
    this.activitySummary,
  });

  @override
  List<Object?> get props => [
        stats,
        services,
        memberCountsByType,
        connectionCount,
        connectedProviderTypes,
        memoryCount,
        latestInsight,
        reportSummary,
        activitySummary,
      ];

  ProfileLoaded copyWith({
    UserStats? stats,
    SmartServicesSummary? services,
    Map<String, int>? memberCountsByType,
    int? connectionCount,
    List<String>? connectedProviderTypes,
    int? memoryCount,
    String? latestInsight,
    Map<String, dynamic>? reportSummary,
    ActivitySummary? activitySummary,
  }) {
    return ProfileLoaded(
      stats: stats ?? this.stats,
      services: services ?? this.services,
      memberCountsByType: memberCountsByType ?? this.memberCountsByType,
      connectionCount: connectionCount ?? this.connectionCount,
      connectedProviderTypes:
          connectedProviderTypes ?? this.connectedProviderTypes,
      memoryCount: memoryCount ?? this.memoryCount,
      latestInsight: latestInsight ?? this.latestInsight,
      reportSummary: reportSummary ?? this.reportSummary,
      activitySummary: activitySummary ?? this.activitySummary,
    );
  }

  int get totalMemberCount {
    int total = 0;
    for (final count in memberCountsByType.values) {
      total += count;
    }
    return total;
  }

  int get weeklyTaskCount =>
      (reportSummary['total_tasks'] as num?)?.toInt() ?? 0;

  int get reportMemoryCount =>
      (reportSummary['memories'] as num?)?.toInt() ?? 0;

  int get reportEventCount =>
      (reportSummary['events'] as num?)?.toInt() ?? 0;

  int get reportInsightCount =>
      (reportSummary['insights'] as num?)?.toInt() ?? 0;

  int get reportReminderCount =>
      (reportSummary['reminders'] as num?)?.toInt() ?? 0;
}

class ProfileError extends ProfileState {
  final String message;

  const ProfileError(this.message);

  @override
  List<Object?> get props => [message];
}

class ServiceOperationInProgress extends ProfileState {
  final String serviceId;
  final ProfileLoaded previousState;

  const ServiceOperationInProgress({
    required this.serviceId,
    required this.previousState,
  });

  @override
  List<Object?> get props => [serviceId, previousState];
}

class ServiceOperationSuccess extends ProfileState {
  final String message;
  final ProfileLoaded currentState;

  const ServiceOperationSuccess({
    required this.message,
    required this.currentState,
  });

  @override
  List<Object?> get props => [message, currentState];
}

// BLoC
class ProfileBloc extends Bloc<ProfileEvent, ProfileState> {
  final ProfileRepository repository;
  final ProfileRemoteDataSource remoteDataSource;

  UserStats? _cachedStats;
  SmartServicesSummary? _cachedServices;
  Map<String, int> _cachedMemberCounts = {};
  int _cachedConnectionCount = 0;
  List<String> _cachedConnectedProviderTypes = [];
  int _cachedMemoryCount = 0;
  String? _cachedLatestInsight;
  Map<String, dynamic> _cachedReportSummary = {};
  ActivitySummary? _cachedActivitySummary;

  ProfileBloc({
    required this.repository,
    required this.remoteDataSource,
  }) : super(const ProfileInitial()) {
    on<ProfileLoadRequested>(_onLoadRequested);
    on<ProfileRefreshRequested>(_onRefreshRequested);
    on<SmartServiceToggled>(_onServiceToggled);
    on<SmartServiceTriggered>(_onServiceTriggered);
  }

  Future<void> _onLoadRequested(
    ProfileLoadRequested event,
    Emitter<ProfileState> emit,
  ) async {
    emit(const ProfileLoading());
    await _loadAllData(emit);
  }

  Future<void> _onRefreshRequested(
    ProfileRefreshRequested event,
    Emitter<ProfileState> emit,
  ) async {
    await _loadAllData(emit);
  }

  Future<void> _loadAllData(Emitter<ProfileState> emit) async {
    // Load all data in parallel
    final results = await Future.wait([
      repository.getUserStats(),
      repository.getSmartServices(),
      remoteDataSource.fetchMemberStats(),
      remoteDataSource.fetchConnectionSummary(),
      remoteDataSource.fetchMemoryStats(),
      remoteDataSource.fetchReportSummary(range: 'week'),
      remoteDataSource.fetchLatestInsight(),
    ]);

    // Handle stats result
    final statsResult = results[0];
    (statsResult as dynamic).fold(
      (failure) {
        _cachedStats ??= UserStats.empty();
      },
      (stats) {
        _cachedStats = stats as UserStats;
      },
    );

    // Handle services result
    final servicesResult = results[1];
    (servicesResult as dynamic).fold(
      (failure) {
        _cachedServices ??= SmartServicesSummary.empty();
      },
      (services) {
        _cachedServices = services as SmartServicesSummary;
      },
    );

    _cachedMemberCounts = results[2] as Map<String, int>;
    final connSummary = results[3] as Map<String, dynamic>;
    _cachedConnectionCount = connSummary['count'] as int;
    _cachedConnectedProviderTypes =
        (connSummary['provider_types'] as List<dynamic>).cast<String>();
    _cachedMemoryCount = results[4] as int;
    _cachedReportSummary = results[5] as Map<String, dynamic>;
    _cachedLatestInsight = results[6] as String?;

    // Build ActivitySummary from report summary data
    final breakdown = _cachedReportSummary['breakdown'] as Map<String, dynamic>? ?? {};
    _cachedActivitySummary = ActivitySummary(
      totalTasksCompleted:
          (_cachedReportSummary['total_actions'] as num?)?.toInt() ?? 0,
      remindersSent:
          (breakdown['reminders_sent'] as num?)?.toInt() ?? 0,
      giftsRecommended:
          (breakdown['gifts_tracked'] as num?)?.toInt() ?? 0,
      priceAlerts:
          (breakdown['insights_generated'] as num?)?.toInt() ?? 0,
      holidaysSynced:
          (breakdown['briefings_run'] as num?)?.toInt() ?? 0,
      period: 'week',
    );

    if (_cachedStats != null && _cachedServices != null) {
      emit(ProfileLoaded(
        stats: _cachedStats!,
        services: _cachedServices!,
        memberCountsByType: _cachedMemberCounts,
        connectionCount: _cachedConnectionCount,
        connectedProviderTypes: _cachedConnectedProviderTypes,
        memoryCount: _cachedMemoryCount,
        latestInsight: _cachedLatestInsight,
        reportSummary: _cachedReportSummary,
        activitySummary: _cachedActivitySummary,
      ));
    } else {
      emit(const ProfileError('加载个人信息失败'));
    }
  }

  Future<void> _onServiceToggled(
    SmartServiceToggled event,
    Emitter<ProfileState> emit,
  ) async {
    final currentState = state;
    if (currentState is! ProfileLoaded) return;

    emit(ServiceOperationInProgress(
      serviceId: event.serviceId,
      previousState: currentState,
    ));

    final result = event.enable
        ? await repository.resumeService(event.serviceId)
        : await repository.pauseService(event.serviceId);

    await result.fold(
      (failure) async {
        emit(currentState);
        emit(ProfileError(failure.message));
      },
      (_) async {
        // Refresh services after toggle
        final servicesResult = await repository.getSmartServices();
        servicesResult.fold(
          (failure) {
            emit(currentState);
          },
          (services) {
            _cachedServices = services;
            final newState = currentState.copyWith(services: services);
            emit(ServiceOperationSuccess(
              message: event.enable ? '服务已启动' : '服务已暂停',
              currentState: newState,
            ));
            emit(newState);
          },
        );
      },
    );
  }

  Future<void> _onServiceTriggered(
    SmartServiceTriggered event,
    Emitter<ProfileState> emit,
  ) async {
    final currentState = state;
    if (currentState is! ProfileLoaded) return;

    emit(ServiceOperationInProgress(
      serviceId: event.serviceId,
      previousState: currentState,
    ));

    final result =
        await repository.triggerServiceJob(event.serviceId, event.jobName);

    await result.fold(
      (failure) async {
        emit(currentState);
        emit(ProfileError(failure.message));
      },
      (_) async {
        // Refresh services after trigger
        final servicesResult = await repository.getSmartServices();
        servicesResult.fold(
          (failure) {
            emit(currentState);
          },
          (services) {
            _cachedServices = services;
            final newState = currentState.copyWith(services: services);
            emit(ServiceOperationSuccess(
              message: '任务已触发',
              currentState: newState,
            ));
            emit(newState);
          },
        );
      },
    );
  }
}
