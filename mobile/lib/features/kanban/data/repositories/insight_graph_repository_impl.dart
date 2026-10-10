import '../../domain/entities/insight_graph_data.dart';
import '../../domain/repositories/insight_graph_repository.dart';
import '../datasources/insight_graph_remote_datasource.dart';

/// 动态图谱仓库实现
class InsightGraphRepositoryImpl implements InsightGraphRepository {
  final InsightGraphRemoteDataSource _remoteDataSource;

  InsightGraphRepositoryImpl({
    required InsightGraphRemoteDataSource remoteDataSource,
  }) : _remoteDataSource = remoteDataSource;

  @override
  Future<InsightGraphData?> getInsightGraph({DateTime? targetDate}) async {
    return _remoteDataSource.fetchInsightGraph(targetDate: targetDate);
  }

  @override
  Future<InsightGraphData?> getInsightGraphForEvent(String eventId) async {
    return _remoteDataSource.fetchInsightGraphForEvent(eventId);
  }

  @override
  Future<void> dismissItem(String itemId, {String? correction}) async {
    await _remoteDataSource.postItemAction(
      itemId, 'dismiss', correction: correction,
    );
  }

  @override
  Future<void> confirmItem(String itemId, {DateTime? scheduledStart}) async {
    await _remoteDataSource.postItemAction(
      itemId, 'confirm', scheduledStart: scheduledStart,
    );
  }

  @override
  Future<void> snoozeItem(String itemId, Duration duration) async {
    await _remoteDataSource.postItemAction(
      itemId,
      'snooze:${duration.inMinutes}',
    );
  }

  @override
  Future<void> dismissAlert(String alertId) async {
    await _remoteDataSource.postAlertAction(alertId, 'dismiss');
  }

  @override
  Future<List<TripSummary>> getUpcomingTrips({int limit = 5}) async {
    return _remoteDataSource.fetchUpcomingTrips(limit: limit);
  }

  @override
  Future<EventGraphResponse> getEventGraph(String tripId) async {
    return _remoteDataSource.fetchEventGraph(tripId);
  }

  @override
  Future<Map<String, dynamic>> confirmPendingAction(
    String actionId, {
    DateTime? newStart,
    DateTime? newEnd,
  }) async {
    return _remoteDataSource.confirmPendingAction(
      actionId,
      newStart: newStart,
      newEnd: newEnd,
    );
  }

  @override
  Future<void> rejectPendingAction(String actionId) async {
    await _remoteDataSource.rejectPendingAction(actionId);
  }

  @override
  Future<void> createAssociation({
    required String eventId,
    required String targetType,
    required String targetId,
    required String associationType,
    required String title,
    required String reason,
    String priority = 'convenient',
  }) async {
    await _remoteDataSource.createAssociation(
      eventId: eventId,
      targetType: targetType,
      targetId: targetId,
      associationType: associationType,
      title: title,
      reason: reason,
      priority: priority,
    );
  }
}
