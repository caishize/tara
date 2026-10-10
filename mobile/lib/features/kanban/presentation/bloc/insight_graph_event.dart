import 'package:equatable/equatable.dart';

import '../../domain/entities/associated_item.dart';

/// 动态图谱事件基类
abstract class InsightGraphEvent extends Equatable {
  const InsightGraphEvent();

  @override
  List<Object?> get props => [];
}

/// 加载动态图谱
class LoadInsightGraph extends InsightGraphEvent {
  final DateTime? targetDate;

  const LoadInsightGraph({this.targetDate});

  @override
  List<Object?> get props => [targetDate];
}

/// 加载特定事件的动态图谱
class LoadInsightGraphForEvent extends InsightGraphEvent {
  final String eventId;

  const LoadInsightGraphForEvent(this.eventId);

  @override
  List<Object?> get props => [eventId];
}

/// 刷新动态图谱
class RefreshInsightGraph extends InsightGraphEvent {
  const RefreshInsightGraph();
}

/// 按类型筛选
class FilterByType extends InsightGraphEvent {
  final ItemType? type; // null 表示全部

  const FilterByType(this.type);

  @override
  List<Object?> get props => [type];
}

/// 忽略事项
class DismissItem extends InsightGraphEvent {
  final String itemId;
  final String? correction; // 用户纠正，如"外婆不在澳门"

  const DismissItem(this.itemId, {this.correction});

  @override
  List<Object?> get props => [itemId, correction];
}

/// 确认事项
class ConfirmItem extends InsightGraphEvent {
  final String itemId;
  final DateTime? scheduledStart; // 用户选择的日期时间

  const ConfirmItem(this.itemId, {this.scheduledStart});

  @override
  List<Object?> get props => [itemId, scheduledStart];
}

/// 延后事项
class SnoozeItem extends InsightGraphEvent {
  final String itemId;
  final Duration duration;

  const SnoozeItem(this.itemId, this.duration);

  @override
  List<Object?> get props => [itemId, duration];
}

/// 忽略提醒
class DismissAlert extends InsightGraphEvent {
  final String alertId;

  const DismissAlert(this.alertId);

  @override
  List<Object?> get props => [alertId];
}

/// PRD 2.3.2: 加载即将到来的行程列表（用于切换）
class LoadUpcomingTrips extends InsightGraphEvent {
  const LoadUpcomingTrips();
}

/// PRD 2.3.2: 切换到指定行程
class SwitchTrip extends InsightGraphEvent {
  final String tripId;

  const SwitchTrip(this.tripId);

  @override
  List<Object?> get props => [tripId];
}

/// PRD 2.3.2: 加载指定行程的事件图谱
class LoadTripGraph extends InsightGraphEvent {
  final String tripId;

  const LoadTripGraph(this.tripId);

  @override
  List<Object?> get props => [tripId];
}

/// 冲突解决操作类型
enum ConflictResolutionAction { confirm, reject }

/// 解决冲突 (确认/拒绝待处理操作)
class ResolveConflict extends InsightGraphEvent {
  final String alertId;
  final String pendingActionId;
  final ConflictResolutionAction action;
  final DateTime? newStart;
  final DateTime? newEnd;

  const ResolveConflict({
    required this.alertId,
    required this.pendingActionId,
    required this.action,
    this.newStart,
    this.newEnd,
  });

  @override
  List<Object?> get props => [alertId, pendingActionId, action, newStart, newEnd];
}

/// 按分类筛选关联 (人物、待办、人情、地点、历史、人情往来)
class FilterByCategory extends InsightGraphEvent {
  final String category;

  const FilterByCategory({required this.category});

  @override
  List<Object?> get props => [category];
}

/// 清除筛选
class ClearFilter extends InsightGraphEvent {
  const ClearFilter();
}

/// 执行图谱节点上的操作按钮
class ExecuteNodeAction extends InsightGraphEvent {
  final String actionType;
  final String associationId;
  final Map<String, dynamic> targetData;

  const ExecuteNodeAction({
    required this.actionType,
    required this.associationId,
    required this.targetData,
  });

  @override
  List<Object?> get props => [actionType, associationId, targetData];
}
