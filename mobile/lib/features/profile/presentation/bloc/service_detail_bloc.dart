import 'package:equatable/equatable.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../data/datasources/profile_remote_datasource.dart';
import '../../domain/entities/smart_service.dart';
import '../../domain/entities/service_execution.dart';

// Events
abstract class ServiceDetailEvent extends Equatable {
  const ServiceDetailEvent();

  @override
  List<Object?> get props => [];
}

class ServiceDetailLoadRequested extends ServiceDetailEvent {
  final String serviceId;

  const ServiceDetailLoadRequested(this.serviceId);

  @override
  List<Object?> get props => [serviceId];
}

class ServiceManualTriggerRequested extends ServiceDetailEvent {
  final String serviceId;

  const ServiceManualTriggerRequested(this.serviceId);

  @override
  List<Object?> get props => [serviceId];
}

// States
abstract class ServiceDetailState extends Equatable {
  const ServiceDetailState();

  @override
  List<Object?> get props => [];
}

class ServiceDetailInitial extends ServiceDetailState {
  const ServiceDetailInitial();
}

class ServiceDetailLoading extends ServiceDetailState {
  const ServiceDetailLoading();
}

class ServiceDetailLoaded extends ServiceDetailState {
  final SmartService? service;
  final ExecutionHistory executionHistory;

  const ServiceDetailLoaded({
    this.service,
    required this.executionHistory,
  });

  @override
  List<Object?> get props => [service, executionHistory];
}

class ServiceDetailError extends ServiceDetailState {
  final String message;

  const ServiceDetailError(this.message);

  @override
  List<Object?> get props => [message];
}

class ServiceTriggerInProgress extends ServiceDetailState {
  final SmartService? service;
  final ExecutionHistory previousHistory;

  const ServiceTriggerInProgress({
    this.service,
    required this.previousHistory,
  });

  @override
  List<Object?> get props => [service, previousHistory];
}

class ServiceTriggerSuccess extends ServiceDetailState {
  final SmartService? service;
  final ExecutionHistory executionHistory;
  final String executionId;

  const ServiceTriggerSuccess({
    this.service,
    required this.executionHistory,
    required this.executionId,
  });

  @override
  List<Object?> get props => [service, executionHistory, executionId];
}

// BLoC
class ServiceDetailBloc extends Bloc<ServiceDetailEvent, ServiceDetailState> {
  final ProfileRemoteDataSource _remoteDataSource;

  SmartService? _currentService;
  ExecutionHistory _currentHistory = ExecutionHistory.empty();

  ServiceDetailBloc(this._remoteDataSource)
      : super(const ServiceDetailInitial()) {
    on<ServiceDetailLoadRequested>(_onLoadRequested);
    on<ServiceManualTriggerRequested>(_onManualTriggerRequested);
  }

  Future<void> _onLoadRequested(
    ServiceDetailLoadRequested event,
    Emitter<ServiceDetailState> emit,
  ) async {
    emit(const ServiceDetailLoading());

    try {
      // Fetch execution history for this scheduler
      final history = await _remoteDataSource.getExecutionHistory(
        schedulerName: event.serviceId,
        limit: 50,
      );

      _currentHistory = history;

      // Try to get updated service info
      try {
        final services = await _remoteDataSource.getSmartServices();
        _currentService = services.services.firstWhere(
          (s) => s.id == event.serviceId,
          orElse: () => services.services.first,
        );
      } catch (e) {
        // Service info fetch failed, continue with history only
      }

      emit(ServiceDetailLoaded(
        service: _currentService,
        executionHistory: history,
      ));
    } catch (e) {
      emit(ServiceDetailError('加载失败: ${e.toString()}'));
    }
  }

  Future<void> _onManualTriggerRequested(
    ServiceManualTriggerRequested event,
    Emitter<ServiceDetailState> emit,
  ) async {
    emit(ServiceTriggerInProgress(
      service: _currentService,
      previousHistory: _currentHistory,
    ));

    try {
      // Get the first job name from the scheduler
      final detail =
          await _remoteDataSource.getSchedulerDetail(event.serviceId);
      final jobs = detail['jobs'] as List<dynamic>? ?? [];

      if (jobs.isEmpty) {
        emit(ServiceDetailError('该服务没有可执行的任务'));
        return;
      }

      // Trigger the first job
      final firstJobName = jobs.first['name'] as String;
      final result = await _remoteDataSource.triggerServiceJob(
        event.serviceId,
        firstJobName,
      );

      // Wait a moment for execution to complete, then refresh history
      await Future.delayed(const Duration(seconds: 2));

      // Fetch updated history
      final updatedHistory = await _remoteDataSource.getExecutionHistory(
        schedulerName: event.serviceId,
        limit: 50,
      );

      _currentHistory = updatedHistory;

      // Try to refresh service info
      try {
        final services = await _remoteDataSource.getSmartServices();
        _currentService = services.services.firstWhere(
          (s) => s.id == event.serviceId,
          orElse: () => _currentService!,
        );
      } catch (e) {
        // Ignore
      }

      emit(ServiceTriggerSuccess(
        service: _currentService,
        executionHistory: updatedHistory,
        executionId: result['execution_id'] as String? ?? '',
      ));
    } catch (e) {
      emit(ServiceDetailError('执行失败: ${e.toString()}'));
      // Return to loaded state
      emit(ServiceDetailLoaded(
        service: _currentService,
        executionHistory: _currentHistory,
      ));
    }
  }
}
