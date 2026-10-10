import '../entities/insight_graph_data.dart';
import '../../data/datasources/insight_graph_remote_datasource.dart';

/// 动态图谱仓库接口
abstract class InsightGraphRepository {
  /// 获取基于日期的动态图谱数据
  /// [targetDate] 目标日期，为空则返回最近的核心事件
  Future<InsightGraphData?> getInsightGraph({DateTime? targetDate});

  /// 获取基于特定事件的动态图谱数据
  /// [eventId] 事件ID
  Future<InsightGraphData?> getInsightGraphForEvent(String eventId);

  /// 获取即将到来的行程列表
  Future<List<TripSummary>> getUpcomingTrips({int limit = 5});

  /// 获取行程的事件图谱
  Future<EventGraphResponse> getEventGraph(String tripId);

  /// 忽略/取消某个关联事项
  /// [itemId] 事项ID
  /// [correction] 用户纠正信息（如"外婆不在澳门"）
  Future<void> dismissItem(String itemId, {String? correction});

  /// 确认某个关联事项
  /// [itemId] 事项ID
  /// [scheduledStart] 用户选择的安排时间
  Future<void> confirmItem(String itemId, {DateTime? scheduledStart});

  /// 延后某个关联事项
  /// [itemId] 事项ID
  /// [duration] 延后时间
  Future<void> snoozeItem(String itemId, Duration duration);

  /// 忽略某个提醒
  /// [alertId] 提醒ID
  Future<void> dismissAlert(String alertId);

  /// 确认冲突解决的待处理操作
  Future<Map<String, dynamic>> confirmPendingAction(
    String actionId, {
    DateTime? newStart,
    DateTime? newEnd,
  });

  /// 拒绝冲突解决的待处理操作
  Future<void> rejectPendingAction(String actionId);

  /// 创建关联
  Future<void> createAssociation({
    required String eventId,
    required String targetType,
    required String targetId,
    required String associationType,
    required String title,
    required String reason,
    String priority = 'convenient',
  });
}
