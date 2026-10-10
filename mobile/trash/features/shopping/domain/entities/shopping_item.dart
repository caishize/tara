import 'package:equatable/equatable.dart';
import 'package:flutter/material.dart';

/// 商品标签
enum ItemTag {
  daily,        // 日常采购
  businessTrip, // 出差代购
  gift,         // 礼物
  urgent,       // 紧急
}

/// 商品状态
enum ItemStatus {
  pending,    // 待购买
  ordered,    // 已下单
  inTransit,  // 配送中
  delivered,  // 已送达
  cancelled,  // 已取消
}

/// 物流更新记录
class TrackingUpdate extends Equatable {
  final DateTime timestamp;
  final String status;
  final String? location;
  final String description;

  const TrackingUpdate({
    required this.timestamp,
    required this.status,
    this.location,
    required this.description,
  });

  @override
  List<Object?> get props => [timestamp, status, location, description];
}

/// 商品分类
enum ItemCategory {
  dairy,        // 乳制品
  meat,         // 肉类
  seafood,      // 海鲜
  vegetable,    // 蔬菜
  fruit,        // 水果
  grain,        // 粮油
  snack,        // 零食
  beverage,     // 饮料
  household,    // 家居日用
  personal,     // 个护美妆
  baby,         // 母婴用品
  pet,          // 宠物用品
  electronics,  // 电子产品
  clothing,     // 服装
  other,        // 其他
}

/// 商品来源类型
enum ItemSourceType {
  manual,           // 手动添加
  giftRecommendation, // 礼物推荐
  travelPrep,       // 旅行准备
  aiGenerated,      // AI生成
  replenishment,    // 补货提醒
}

/// 购物商品实体
class ShoppingItem extends Equatable {
  final String id;
  final String listId;
  final String productName;
  final ItemCategory? category;
  final double quantity;
  final String? unit;
  final int priority; // 1-5, 1最高
  final double? estimatedPrice;
  final double? actualPrice;
  final bool isPurchased;
  final String? purchasedBy;
  final DateTime? purchasedAt;
  final String? merchant;
  final String? notes;
  final ItemSourceType sourceType;
  final String? giftRecommendationId;
  final String? travelPlanId;
  final DateTime createdAt;
  final DateTime updatedAt;
  // New fields for prototype
  final List<ItemTag> tags;
  final String? assignedTo;
  final String? assignedToName;
  final ItemStatus itemStatus;
  final DateTime? orderDate;
  final DateTime? expectedDeliveryDate;
  final String? trackingNumber;
  final List<TrackingUpdate> trackingUpdates;
  // 关联事件
  final String? eventId;
  final String? eventType; // 'date', 'travel', 'gift'
  final String? eventName; // 事件名称（用于显示）

  const ShoppingItem({
    required this.id,
    required this.listId,
    required this.productName,
    this.category,
    this.quantity = 1,
    this.unit,
    this.priority = 3,
    this.estimatedPrice,
    this.actualPrice,
    this.isPurchased = false,
    this.purchasedBy,
    this.purchasedAt,
    this.merchant,
    this.notes,
    this.sourceType = ItemSourceType.manual,
    this.giftRecommendationId,
    this.travelPlanId,
    required this.createdAt,
    required this.updatedAt,
    // New fields
    this.tags = const [],
    this.assignedTo,
    this.assignedToName,
    this.itemStatus = ItemStatus.pending,
    this.orderDate,
    this.expectedDeliveryDate,
    this.trackingNumber,
    this.trackingUpdates = const [],
    // 关联事件
    this.eventId,
    this.eventType,
    this.eventName,
  });

  /// 价格差异（实际 - 预估）
  double? get priceDifference {
    if (actualPrice == null || estimatedPrice == null) return null;
    return actualPrice! - estimatedPrice!;
  }

  /// 是否超出预算
  bool get isOverBudget {
    final diff = priceDifference;
    return diff != null && diff > 0;
  }

  /// 获取分类显示名称
  String get categoryName {
    if (category == null) return '未分类';
    switch (category!) {
      case ItemCategory.dairy:
        return '乳制品';
      case ItemCategory.meat:
        return '肉类';
      case ItemCategory.seafood:
        return '海鲜';
      case ItemCategory.vegetable:
        return '蔬菜';
      case ItemCategory.fruit:
        return '水果';
      case ItemCategory.grain:
        return '粮油';
      case ItemCategory.snack:
        return '零食';
      case ItemCategory.beverage:
        return '饮料';
      case ItemCategory.household:
        return '家居日用';
      case ItemCategory.personal:
        return '个护美妆';
      case ItemCategory.baby:
        return '母婴用品';
      case ItemCategory.pet:
        return '宠物用品';
      case ItemCategory.electronics:
        return '电子产品';
      case ItemCategory.clothing:
        return '服装';
      case ItemCategory.other:
        return '其他';
    }
  }

  /// 获取分类图标
  String get categoryIcon {
    if (category == null) return '📦';
    switch (category!) {
      case ItemCategory.dairy:
        return '🥛';
      case ItemCategory.meat:
        return '🥩';
      case ItemCategory.seafood:
        return '🐟';
      case ItemCategory.vegetable:
        return '🥬';
      case ItemCategory.fruit:
        return '🍎';
      case ItemCategory.grain:
        return '🌾';
      case ItemCategory.snack:
        return '🍪';
      case ItemCategory.beverage:
        return '🥤';
      case ItemCategory.household:
        return '🏠';
      case ItemCategory.personal:
        return '💄';
      case ItemCategory.baby:
        return '👶';
      case ItemCategory.pet:
        return '🐾';
      case ItemCategory.electronics:
        return '📱';
      case ItemCategory.clothing:
        return '👕';
      case ItemCategory.other:
        return '📦';
    }
  }

  /// 获取优先级显示名称
  String get priorityName {
    switch (priority) {
      case 1:
        return '最高';
      case 2:
        return '高';
      case 3:
        return '普通';
      case 4:
        return '低';
      case 5:
        return '最低';
      default:
        return '普通';
    }
  }

  /// 显示数量和单位
  String get quantityDisplay {
    if (unit != null && unit!.isNotEmpty) {
      return '$quantity $unit';
    }
    return quantity.toString();
  }

  /// 获取商品状态显示名称
  String get itemStatusName {
    switch (itemStatus) {
      case ItemStatus.pending:
        return '待购买';
      case ItemStatus.ordered:
        return '已下单';
      case ItemStatus.inTransit:
        return '配送中';
      case ItemStatus.delivered:
        return '已送达';
      case ItemStatus.cancelled:
        return '已取消';
    }
  }

  /// 获取商品状态图标
  IconData get itemStatusIcon {
    switch (itemStatus) {
      case ItemStatus.pending:
        return Icons.shopping_cart_outlined;
      case ItemStatus.ordered:
        return Icons.receipt_outlined;
      case ItemStatus.inTransit:
        return Icons.local_shipping_outlined;
      case ItemStatus.delivered:
        return Icons.check_circle_outline;
      case ItemStatus.cancelled:
        return Icons.cancel_outlined;
    }
  }

  /// 获取商品状态颜色
  Color get itemStatusColor {
    switch (itemStatus) {
      case ItemStatus.pending:
        return const Color(0xFFFFA726);  // Orange
      case ItemStatus.ordered:
        return const Color(0xFF42A5F5);  // Blue
      case ItemStatus.inTransit:
        return const Color(0xFF66BB6A);  // Green
      case ItemStatus.delivered:
        return const Color(0xFF4CAF50);  // Green success
      case ItemStatus.cancelled:
        return const Color(0xFFEF5350);  // Red
    }
  }

  /// 获取标签显示
  String get tagsDisplay {
    return tags.map((tag) {
      switch (tag) {
        case ItemTag.daily:
          return '日常采购';
        case ItemTag.businessTrip:
          return '出差代购';
        case ItemTag.gift:
          return '礼物';
        case ItemTag.urgent:
          return '紧急';
      }
    }).join('、');
  }

  /// 是否可以取消
  bool get canCancel => itemStatus == ItemStatus.pending || itemStatus == ItemStatus.ordered;

  /// 是否可以标记完成
  bool get canMarkComplete => itemStatus != ItemStatus.delivered && itemStatus != ItemStatus.cancelled;

  /// 获取预计送达文字
  String? get deliveryText {
    if (expectedDeliveryDate == null) return null;
    final now = DateTime.now();
    final diff = expectedDeliveryDate!.difference(DateTime(now.year, now.month, now.day)).inDays;
    if (diff == 0) return '今天到货';
    if (diff == 1) return '明天到货';
    if (diff == 2) return '后天到货';
    if (diff < 0) return '已过期';
    return '$diff天后到货';
  }

  ShoppingItem copyWith({
    String? id,
    String? listId,
    String? productName,
    ItemCategory? category,
    double? quantity,
    String? unit,
    int? priority,
    double? estimatedPrice,
    double? actualPrice,
    bool? isPurchased,
    String? purchasedBy,
    DateTime? purchasedAt,
    String? merchant,
    String? notes,
    ItemSourceType? sourceType,
    String? giftRecommendationId,
    String? travelPlanId,
    DateTime? createdAt,
    DateTime? updatedAt,
    List<ItemTag>? tags,
    String? assignedTo,
    String? assignedToName,
    ItemStatus? itemStatus,
    DateTime? orderDate,
    DateTime? expectedDeliveryDate,
    String? trackingNumber,
    List<TrackingUpdate>? trackingUpdates,
    String? eventId,
    String? eventType,
    String? eventName,
  }) {
    return ShoppingItem(
      id: id ?? this.id,
      listId: listId ?? this.listId,
      productName: productName ?? this.productName,
      category: category ?? this.category,
      quantity: quantity ?? this.quantity,
      unit: unit ?? this.unit,
      priority: priority ?? this.priority,
      estimatedPrice: estimatedPrice ?? this.estimatedPrice,
      actualPrice: actualPrice ?? this.actualPrice,
      isPurchased: isPurchased ?? this.isPurchased,
      purchasedBy: purchasedBy ?? this.purchasedBy,
      purchasedAt: purchasedAt ?? this.purchasedAt,
      merchant: merchant ?? this.merchant,
      notes: notes ?? this.notes,
      sourceType: sourceType ?? this.sourceType,
      giftRecommendationId: giftRecommendationId ?? this.giftRecommendationId,
      travelPlanId: travelPlanId ?? this.travelPlanId,
      createdAt: createdAt ?? this.createdAt,
      updatedAt: updatedAt ?? this.updatedAt,
      tags: tags ?? this.tags,
      assignedTo: assignedTo ?? this.assignedTo,
      assignedToName: assignedToName ?? this.assignedToName,
      itemStatus: itemStatus ?? this.itemStatus,
      orderDate: orderDate ?? this.orderDate,
      expectedDeliveryDate: expectedDeliveryDate ?? this.expectedDeliveryDate,
      trackingNumber: trackingNumber ?? this.trackingNumber,
      trackingUpdates: trackingUpdates ?? this.trackingUpdates,
      eventId: eventId ?? this.eventId,
      eventType: eventType ?? this.eventType,
      eventName: eventName ?? this.eventName,
    );
  }

  /// 是否有关联事件
  bool get hasLinkedEvent => eventId != null && eventType != null;

  /// 获取关联事件显示文字
  String? get linkedEventDisplay {
    if (!hasLinkedEvent) return null;
    if (eventName != null) return eventName;
    switch (eventType) {
      case 'date':
        return '关联日期';
      case 'travel':
        return '关联旅行';
      case 'gift':
        return '关联礼物';
      default:
        return '关联事件';
    }
  }

  /// 获取关联事件图标
  IconData? get linkedEventIcon {
    if (!hasLinkedEvent) return null;
    switch (eventType) {
      case 'date':
        return Icons.event;
      case 'travel':
        return Icons.flight;
      case 'gift':
        return Icons.card_giftcard;
      default:
        return Icons.link;
    }
  }

  @override
  List<Object?> get props => [
    id, listId, productName, category, quantity, unit, priority,
    estimatedPrice, actualPrice, isPurchased, purchasedBy, purchasedAt,
    merchant, notes, sourceType, giftRecommendationId, travelPlanId,
    createdAt, updatedAt, tags, assignedTo, assignedToName, itemStatus,
    orderDate, expectedDeliveryDate, trackingNumber, trackingUpdates,
    eventId, eventType, eventName,
  ];
}
