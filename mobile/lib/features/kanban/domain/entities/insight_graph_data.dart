import 'package:equatable/equatable.dart';

import 'associated_item.dart';
import 'conflict_alert.dart';
import 'core_event.dart';

/// 动态图谱数据聚合实体
class InsightGraphData extends Equatable {
  final CoreEvent coreEvent;
  final List<AssociatedItem> associatedItems;
  final List<ConflictAlert> conflictAlerts;

  const InsightGraphData({
    required this.coreEvent,
    required this.associatedItems,
    required this.conflictAlerts,
  });

  /// 获取所有关联事项的数量
  int get totalAssociatedCount => associatedItems.length;

  /// 获取冲突/提醒的数量
  int get totalAlertCount => conflictAlerts.length;

  /// 获取"可顺便"做的事项数量（强烈推荐 + 顺便）
  int get convenientCount => associatedItems
      .where((item) =>
          item.priority == ItemPriority.stronglyRecommend ||
          item.priority == ItemPriority.convenient)
      .length;

  /// 获取冲突数量
  int get conflictCount =>
      conflictAlerts.where((alert) => alert.isConflict).length;

  /// 按类型筛选关联事项
  List<AssociatedItem> filterByType(ItemType type) {
    return associatedItems.where((item) => item.itemType == type).toList();
  }

  /// 按优先级筛选关联事项
  List<AssociatedItem> filterByPriority(ItemPriority priority) {
    return associatedItems.where((item) => item.priority == priority).toList();
  }

  /// 获取强烈推荐的事项
  List<AssociatedItem> get stronglyRecommendedItems =>
      filterByPriority(ItemPriority.stronglyRecommend);

  /// 获取顺便可做的事项
  List<AssociatedItem> get convenientItems =>
      filterByPriority(ItemPriority.convenient);

  /// 获取可选的事项
  List<AssociatedItem> get optionalItems =>
      filterByPriority(ItemPriority.optional);

  /// 获取人物类事项
  List<AssociatedItem> get personItems => filterByType(ItemType.person);

  /// 获取任务类事项
  List<AssociatedItem> get taskItems => filterByType(ItemType.task);

  /// 获取物品类事项
  List<AssociatedItem> get giftItems => filterByType(ItemType.gift);

  /// 获取高优先级提醒
  List<ConflictAlert> get highPriorityAlerts =>
      conflictAlerts.where((alert) => alert.isHighPriority).toList();

  /// 是否有内容
  bool get hasContent =>
      associatedItems.isNotEmpty || conflictAlerts.isNotEmpty;

  /// 是否为空
  bool get isEmpty => !hasContent;

  /// 创建空的图谱数据
  static InsightGraphData empty(CoreEvent event) {
    return InsightGraphData(
      coreEvent: event,
      associatedItems: const [],
      conflictAlerts: const [],
    );
  }

  /// 创建副本
  InsightGraphData copyWith({
    CoreEvent? coreEvent,
    List<AssociatedItem>? associatedItems,
    List<ConflictAlert>? conflictAlerts,
  }) {
    return InsightGraphData(
      coreEvent: coreEvent ?? this.coreEvent,
      associatedItems: associatedItems ?? this.associatedItems,
      conflictAlerts: conflictAlerts ?? this.conflictAlerts,
    );
  }

  @override
  List<Object?> get props => [coreEvent, associatedItems, conflictAlerts];
}
