import 'package:equatable/equatable.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../data/datasources/profile_remote_datasource.dart';
import '../../domain/entities/secretary_report.dart';
import '../../domain/entities/work_report.dart';

// Events
abstract class WorkReportEvent extends Equatable {
  const WorkReportEvent();

  @override
  List<Object?> get props => [];
}

class WorkReportLoadRequested extends WorkReportEvent {
  final String range;

  const WorkReportLoadRequested({this.range = 'week'});

  @override
  List<Object?> get props => [range];
}

class WorkReportRefreshRequested extends WorkReportEvent {
  const WorkReportRefreshRequested();
}

class CurationDetailRequested extends WorkReportEvent {
  final String jobId;

  const CurationDetailRequested(this.jobId);

  @override
  List<Object?> get props => [jobId];
}

// States
abstract class WorkReportState extends Equatable {
  const WorkReportState();

  @override
  List<Object?> get props => [];
}

class WorkReportInitial extends WorkReportState {
  const WorkReportInitial();
}

class WorkReportLoading extends WorkReportState {
  const WorkReportLoading();
}

class WorkReportLoaded extends WorkReportState {
  final SecretaryReport report;

  const WorkReportLoaded(this.report);

  @override
  List<Object?> get props => [report];
}

class WorkReportError extends WorkReportState {
  final String message;

  const WorkReportError(this.message);

  @override
  List<Object?> get props => [message];
}

class CurationDetailLoading extends WorkReportState {
  const CurationDetailLoading();
}

class CurationDetailLoaded extends WorkReportState {
  final CurationJobDetail detail;

  const CurationDetailLoaded(this.detail);

  @override
  List<Object?> get props => [detail];
}

class CurationDetailError extends WorkReportState {
  final String message;

  const CurationDetailError(this.message);

  @override
  List<Object?> get props => [message];
}

// BLoC
class WorkReportBloc extends Bloc<WorkReportEvent, WorkReportState> {
  final ProfileRemoteDataSource _remoteDataSource;
  String _lastRange = 'week';

  WorkReportBloc(this._remoteDataSource) : super(const WorkReportInitial()) {
    on<WorkReportLoadRequested>(_onLoadRequested);
    on<WorkReportRefreshRequested>(_onRefreshRequested);
    on<CurationDetailRequested>(_onCurationDetailRequested);
  }

  Future<void> _onLoadRequested(
    WorkReportLoadRequested event,
    Emitter<WorkReportState> emit,
  ) async {
    _lastRange = event.range;
    emit(const WorkReportLoading());
    await _loadReport(emit, event.range);
  }

  Future<void> _onRefreshRequested(
    WorkReportRefreshRequested event,
    Emitter<WorkReportState> emit,
  ) async {
    await _loadReport(emit, _lastRange);
  }

  Future<void> _onCurationDetailRequested(
    CurationDetailRequested event,
    Emitter<WorkReportState> emit,
  ) async {
    emit(const CurationDetailLoading());
    try {
      final detail =
          await _remoteDataSource.getCurationJobDetail(event.jobId);
      emit(CurationDetailLoaded(detail));
    } catch (e) {
      emit(CurationDetailError('加载详情失败: ${e.toString()}'));
    }
  }

  Future<void> _loadReport(
    Emitter<WorkReportState> emit,
    String range,
  ) async {
    try {
      final results = await Future.wait([
        _remoteDataSource.fetchReportSummary(range: range),
        _remoteDataSource.fetchReportTimeline(range: range, limit: 20),
      ]);

      final summaryJson = results[0] as Map<String, dynamic>;
      final timelineJson = results[1] as List<Map<String, dynamic>>;

      final summary = summaryJson.isEmpty
          ? ReportSummary.empty()
          : ReportSummary.fromJson(summaryJson);

      final timeline = timelineJson
          .map((item) => ReportTimelineItem.fromJson(item))
          .toList();

      emit(WorkReportLoaded(SecretaryReport(
        summary: summary,
        timeline: timeline,
      )));
    } catch (e) {
      emit(WorkReportError('加载工作报告失败: ${e.toString()}'));
    }
  }
}
