import 'package:equatable/equatable.dart';

/// 关联事项类型
enum ItemType {
  person,   // 人物
  task,     // 任务
  gift,     // 礼物/物品
  place,    // 地点
  business, // 商务/企业
}

/// 优先级枚举
enum ItemPriority {
  stronglyRecommend,  // 强烈推荐
  convenient,         // 顺便
  optional,           // 可选
}

/// 关联事项实体 - 与核心事件相关的人/事/物
class AssociatedItem extends Equatable {
  final String id;
  final String title;
  final String? subtitle;
  final ItemType itemType;
  final ItemPriority priority;
  final String? contextHint;      // 智能提示（如记忆引用）
  final String? relatedMemberId;  // 关联的家庭成员ID
  final String? iconUrl;          // 图标URL
  final Map<String, dynamic>? metadata;

  const AssociatedItem({
    required this.id,
    required this.title,
    this.subtitle,
    required this.itemType,
    required this.priority,
    this.contextHint,
    this.relatedMemberId,
    this.iconUrl,
    this.metadata,
  });

  /// 获取事项类型的中文显示名称
  String get itemTypeDisplayName {
    switch (itemType) {
      case ItemType.person:
        return '人物';
      case ItemType.task:
        return '任务';
      case ItemType.gift:
        return '物品';
      case ItemType.place:
        return '地点';
      case ItemType.business:
        return '商务';
    }
  }

  /// 获取优先级的中文显示名称
  String get priorityDisplayName {
    switch (priority) {
      case ItemPriority.stronglyRecommend:
        return '强烈推荐';
      case ItemPriority.convenient:
        return '顺便';
      case ItemPriority.optional:
        return '可选';
    }
  }

  /// 是否有上下文提示
  bool get hasContextHint => contextHint != null && contextHint!.isNotEmpty;

  /// 是否关联家庭成员
  bool get hasMemberLink => relatedMemberId != null;

  /// 创建副本
  AssociatedItem copyWith({
    String? id,
    String? title,
    String? subtitle,
    ItemType? itemType,
    ItemPriority? priority,
    String? contextHint,
    String? relatedMemberId,
    String? iconUrl,
    Map<String, dynamic>? metadata,
  }) {
    return AssociatedItem(
      id: id ?? this.id,
      title: title ?? this.title,
      subtitle: subtitle ?? this.subtitle,
      itemType: itemType ?? this.itemType,
      priority: priority ?? this.priority,
      contextHint: contextHint ?? this.contextHint,
      relatedMemberId: relatedMemberId ?? this.relatedMemberId,
      iconUrl: iconUrl ?? this.iconUrl,
      metadata: metadata ?? this.metadata,
    );
  }

  @override
  List<Object?> get props => [
        id,
        title,
        subtitle,
        itemType,
        priority,
        contextHint,
        relatedMemberId,
        iconUrl,
        metadata,
      ];
}
