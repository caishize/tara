import '../../domain/entities/associated_item.dart';

/// AssociatedItem 数据模型 - 用于 API 通信
class AssociatedItemModel extends AssociatedItem {
  const AssociatedItemModel({
    required super.id,
    required super.title,
    super.subtitle,
    required super.itemType,
    required super.priority,
    super.contextHint,
    super.relatedMemberId,
    super.iconUrl,
    super.metadata,
  });

  /// 从 JSON 创建模型
  factory AssociatedItemModel.fromJson(Map<String, dynamic> json) {
    return AssociatedItemModel(
      id: json['id'] as String,
      title: json['title'] as String,
      subtitle: json['subtitle'] as String?,
      itemType: _parseItemType(json['item_type'] as String?),
      priority: _parsePriority(json['priority'] as String?),
      contextHint: json['context_hint'] as String?,
      relatedMemberId: json['related_member_id'] as String?,
      iconUrl: json['icon_url'] as String?,
      metadata: json['metadata'] as Map<String, dynamic>?,
    );
  }

  /// 转换为 JSON
  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'title': title,
      'subtitle': subtitle,
      'item_type': _itemTypeToString(itemType),
      'priority': _priorityToString(priority),
      'context_hint': contextHint,
      'related_member_id': relatedMemberId,
      'icon_url': iconUrl,
      'metadata': metadata,
    };
  }

  /// 从实体创建模型
  factory AssociatedItemModel.fromEntity(AssociatedItem entity) {
    return AssociatedItemModel(
      id: entity.id,
      title: entity.title,
      subtitle: entity.subtitle,
      itemType: entity.itemType,
      priority: entity.priority,
      contextHint: entity.contextHint,
      relatedMemberId: entity.relatedMemberId,
      iconUrl: entity.iconUrl,
      metadata: entity.metadata,
    );
  }

  static ItemType _parseItemType(String? type) {
    switch (type) {
      case 'person':
        return ItemType.person;
      case 'task':
        return ItemType.task;
      case 'gift':
        return ItemType.gift;
      case 'place':
        return ItemType.place;
      case 'business':
        return ItemType.business;
      default:
        return ItemType.task;
    }
  }

  static String _itemTypeToString(ItemType type) {
    switch (type) {
      case ItemType.person:
        return 'person';
      case ItemType.task:
        return 'task';
      case ItemType.gift:
        return 'gift';
      case ItemType.place:
        return 'place';
      case ItemType.business:
        return 'business';
    }
  }

  static ItemPriority _parsePriority(String? priority) {
    switch (priority) {
      case 'strongly_recommend':
        return ItemPriority.stronglyRecommend;
      case 'convenient':
        return ItemPriority.convenient;
      case 'optional':
        return ItemPriority.optional;
      default:
        return ItemPriority.optional;
    }
  }

  static String _priorityToString(ItemPriority priority) {
    switch (priority) {
      case ItemPriority.stronglyRecommend:
        return 'strongly_recommend';
      case ItemPriority.convenient:
        return 'convenient';
      case ItemPriority.optional:
        return 'optional';
    }
  }
}
