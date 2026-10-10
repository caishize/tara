import 'package:equatable/equatable.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../data/datasources/profile_remote_datasource.dart';
import '../../data/models/activity_record_model.dart';
import '../../domain/entities/activity_record.dart';
import '../../domain/entities/service_execution.dart';

// Events
abstract class ActivityEvent extends Equatable {
  const ActivityEvent();

  @override
  List<Object?> get props => [];
}

class ActivityLoadRequested extends ActivityEvent {
  const ActivityLoadRequested();
}

class ActivityRefreshRequested extends ActivityEvent {
  const ActivityRefreshRequested();
}

// States
abstract class ActivityState extends Equatable {
  const ActivityState();

  @override
  List<Object?> get props => [];
}

class ActivityInitial extends ActivityState {
  const ActivityInitial();
}

class ActivityLoading extends ActivityState {
  const ActivityLoading();
}

class ActivityLoaded extends ActivityState {
  final ActivityTimeline timeline;

  const ActivityLoaded(this.timeline);

  @override
  List<Object?> get props => [timeline];
}

class ActivityError extends ActivityState {
  final String message;

  const ActivityError(this.message);

  @override
  List<Object?> get props => [message];
}

// BLoC
class ActivityBloc extends Bloc<ActivityEvent, ActivityState> {
  final ProfileRemoteDataSource _remoteDataSource;

  ActivityBloc(this._remoteDataSource) : super(const ActivityInitial()) {
    on<ActivityLoadRequested>(_onLoadRequested);
    on<ActivityRefreshRequested>(_onRefreshRequested);
  }

  Future<void> _onLoadRequested(
    ActivityLoadRequested event,
    Emitter<ActivityState> emit,
  ) async {
    emit(const ActivityLoading());
    await _loadActivities(emit);
  }

  Future<void> _onRefreshRequested(
    ActivityRefreshRequested event,
    Emitter<ActivityState> emit,
  ) async {
    await _loadActivities(emit);
  }

  Future<void> _loadActivities(Emitter<ActivityState> emit) async {
    try {
      // Fetch execution history from the last week
      final history = await _remoteDataSource.getExecutionHistory(
        limit: 100,
        offset: 0,
      );

      // Convert executions to activity records
      final activities = <ActivityRecord>[];
      final executionMaps = <Map<String, dynamic>>[];

      for (var execution in history.executions) {
        // Only include completed executions
        if (execution.status == ExecutionStatus.completed) {
          final activityMap = {
            'id': execution.id,
            'scheduler_name': execution.schedulerName,
            'job_name': execution.jobName,
            'status': 'completed',
            'result_summary': execution.resultSummary,
            'created_at': execution.createdAt.toIso8601String(),
          };

          executionMaps.add(activityMap);
          activities.add(ActivityRecordModel.fromExecution(activityMap));
        }
      }

      // Create summary from executions
      final summary = ActivitySummaryModel.fromExecutions(executionMaps);

      final timeline = ActivityTimeline(
        activities: activities,
        summary: summary,
      );

      emit(ActivityLoaded(timeline));
    } catch (e) {
      emit(ActivityError('加载活动记录失败: ${e.toString()}'));
    }
  }
}
