import '../../domain/entities/shopping_item.dart';

class TrackingUpdateModel extends TrackingUpdate {
  const TrackingUpdateModel({
    required super.timestamp,
    required super.status,
    super.location,
    required super.description,
  });

  factory TrackingUpdateModel.fromJson(Map<String, dynamic> json) {
    return TrackingUpdateModel(
      timestamp: DateTime.tryParse(json['timestamp'] ?? '') ?? DateTime.now(),
      status: json['status'] ?? '',
      location: json['location'],
      description: json['description'] ?? '',
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'timestamp': timestamp.toIso8601String(),
      'status': status,
      'location': location,
      'description': description,
    };
  }
}

class ShoppingItemModel extends ShoppingItem {
  const ShoppingItemModel({
    required super.id,
    required super.listId,
    required super.productName,
    super.category,
    super.quantity,
    super.unit,
    super.priority,
    super.estimatedPrice,
    super.actualPrice,
    super.isPurchased,
    super.purchasedBy,
    super.purchasedAt,
    super.merchant,
    super.notes,
    super.sourceType,
    super.giftRecommendationId,
    super.travelPlanId,
    required super.createdAt,
    required super.updatedAt,
    // New fields
    super.tags,
    super.assignedTo,
    super.assignedToName,
    super.itemStatus,
    super.orderDate,
    super.expectedDeliveryDate,
    super.trackingNumber,
    super.trackingUpdates,
    // 关联事件
    super.eventId,
    super.eventType,
    super.eventName,
  });

  factory ShoppingItemModel.fromJson(Map<String, dynamic> json) {
    return ShoppingItemModel(
      id: json['id']?.toString() ?? json['item_id']?.toString() ?? '',
      listId: json['list_id']?.toString() ?? '',
      productName: json['product_name'] ?? '',
      category: _parseCategory(json['category']),
      quantity: (json['quantity'] ?? 1).toDouble(),
      unit: json['unit'],
      priority: json['priority'] ?? 3,
      estimatedPrice: json['estimated_price']?.toDouble(),
      actualPrice: json['actual_price']?.toDouble(),
      isPurchased: json['is_purchased'] ?? false,
      purchasedBy: json['purchased_by']?.toString(),
      purchasedAt: json['purchased_at'] != null ? DateTime.tryParse(json['purchased_at']) : null,
      merchant: json['merchant'],
      notes: json['notes'],
      sourceType: _parseSourceType(json['source_type']),
      giftRecommendationId: json['gift_recommendation_id']?.toString(),
      travelPlanId: json['travel_plan_id']?.toString(),
      createdAt: DateTime.tryParse(json['created_at'] ?? '') ?? DateTime.now(),
      updatedAt: DateTime.tryParse(json['updated_at'] ?? '') ?? DateTime.now(),
      // New fields
      tags: _parseTags(json['tags']),
      assignedTo: json['assigned_to']?.toString(),
      assignedToName: json['assigned_to_name'],
      itemStatus: _parseItemStatus(json['item_status']),
      orderDate: json['order_date'] != null ? DateTime.tryParse(json['order_date']) : null,
      expectedDeliveryDate: json['expected_delivery_date'] != null
          ? DateTime.tryParse(json['expected_delivery_date'])
          : null,
      trackingNumber: json['tracking_number'],
      trackingUpdates: _parseTrackingUpdates(json['tracking_updates']),
      // 关联事件
      eventId: json['event_id']?.toString(),
      eventType: json['event_type'],
      eventName: json['event_name'],
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'list_id': listId,
      'product_name': productName,
      'category': category != null ? _categoryToString(category!) : null,
      'quantity': quantity,
      'unit': unit,
      'priority': priority,
      'estimated_price': estimatedPrice,
      'actual_price': actualPrice,
      'is_purchased': isPurchased,
      'purchased_by': purchasedBy,
      'purchased_at': purchasedAt?.toIso8601String(),
      'merchant': merchant,
      'notes': notes,
      'source_type': _sourceTypeToString(sourceType),
      'gift_recommendation_id': giftRecommendationId,
      'travel_plan_id': travelPlanId,
      'created_at': createdAt.toIso8601String(),
      'updated_at': updatedAt.toIso8601String(),
      // New fields
      'tags': tags.map((t) => _tagToString(t)).toList(),
      'assigned_to': assignedTo,
      'item_status': _itemStatusToString(itemStatus),
      'order_date': orderDate?.toIso8601String(),
      'expected_delivery_date': expectedDeliveryDate?.toIso8601String().split('T')[0],
      'tracking_number': trackingNumber,
      'tracking_updates': trackingUpdates
          .map((t) => (t is TrackingUpdateModel) ? t.toJson() : {
            'timestamp': t.timestamp.toIso8601String(),
            'status': t.status,
            'location': t.location,
            'description': t.description,
          })
          .toList(),
      // 关联事件
      'event_id': eventId,
      'event_type': eventType,
      'event_name': eventName,
    };
  }

  static ItemCategory? _parseCategory(String? category) {
    if (category == null) return null;
    switch (category.toLowerCase()) {
      case 'dairy':
      case '乳制品':
        return ItemCategory.dairy;
      case 'meat':
      case '肉类':
        return ItemCategory.meat;
      case 'seafood':
      case '海鲜':
        return ItemCategory.seafood;
      case 'vegetable':
      case '蔬菜':
        return ItemCategory.vegetable;
      case 'fruit':
      case '水果':
        return ItemCategory.fruit;
      case 'grain':
      case '粮油':
        return ItemCategory.grain;
      case 'snack':
      case '零食':
        return ItemCategory.snack;
      case 'beverage':
      case '饮料':
        return ItemCategory.beverage;
      case 'household':
      case '家居日用':
        return ItemCategory.household;
      case 'personal':
      case '个护美妆':
        return ItemCategory.personal;
      case 'baby':
      case '母婴用品':
        return ItemCategory.baby;
      case 'pet':
      case '宠物用品':
        return ItemCategory.pet;
      case 'electronics':
      case '电子产品':
        return ItemCategory.electronics;
      case 'clothing':
      case '服装':
        return ItemCategory.clothing;
      default:
        return ItemCategory.other;
    }
  }

  static String _categoryToString(ItemCategory category) {
    switch (category) {
      case ItemCategory.dairy:
        return 'dairy';
      case ItemCategory.meat:
        return 'meat';
      case ItemCategory.seafood:
        return 'seafood';
      case ItemCategory.vegetable:
        return 'vegetable';
      case ItemCategory.fruit:
        return 'fruit';
      case ItemCategory.grain:
        return 'grain';
      case ItemCategory.snack:
        return 'snack';
      case ItemCategory.beverage:
        return 'beverage';
      case ItemCategory.household:
        return 'household';
      case ItemCategory.personal:
        return 'personal';
      case ItemCategory.baby:
        return 'baby';
      case ItemCategory.pet:
        return 'pet';
      case ItemCategory.electronics:
        return 'electronics';
      case ItemCategory.clothing:
        return 'clothing';
      case ItemCategory.other:
        return 'other';
    }
  }

  static ItemSourceType _parseSourceType(String? type) {
    switch (type?.toLowerCase()) {
      case 'manual':
        return ItemSourceType.manual;
      case 'gift_recommendation':
        return ItemSourceType.giftRecommendation;
      case 'travel_prep':
        return ItemSourceType.travelPrep;
      case 'ai_generated':
        return ItemSourceType.aiGenerated;
      case 'replenishment':
        return ItemSourceType.replenishment;
      default:
        return ItemSourceType.manual;
    }
  }

  static String _sourceTypeToString(ItemSourceType type) {
    switch (type) {
      case ItemSourceType.manual:
        return 'manual';
      case ItemSourceType.giftRecommendation:
        return 'gift_recommendation';
      case ItemSourceType.travelPrep:
        return 'travel_prep';
      case ItemSourceType.aiGenerated:
        return 'ai_generated';
      case ItemSourceType.replenishment:
        return 'replenishment';
    }
  }

  static List<ItemTag> _parseTags(dynamic tags) {
    if (tags == null || tags is! List) return [];
    return tags
        .map((t) => _parseTag(t as String?))
        .whereType<ItemTag>()
        .toList();
  }

  static ItemTag? _parseTag(String? tag) {
    switch (tag?.toLowerCase()) {
      case 'daily':
        return ItemTag.daily;
      case 'business_trip':
        return ItemTag.businessTrip;
      case 'gift':
        return ItemTag.gift;
      case 'urgent':
        return ItemTag.urgent;
      default:
        return null;
    }
  }

  static String _tagToString(ItemTag tag) {
    switch (tag) {
      case ItemTag.daily:
        return 'daily';
      case ItemTag.businessTrip:
        return 'business_trip';
      case ItemTag.gift:
        return 'gift';
      case ItemTag.urgent:
        return 'urgent';
    }
  }

  static ItemStatus _parseItemStatus(String? status) {
    switch (status?.toLowerCase()) {
      case 'pending':
        return ItemStatus.pending;
      case 'ordered':
        return ItemStatus.ordered;
      case 'in_transit':
        return ItemStatus.inTransit;
      case 'delivered':
        return ItemStatus.delivered;
      case 'cancelled':
        return ItemStatus.cancelled;
      default:
        return ItemStatus.pending;
    }
  }

  static String _itemStatusToString(ItemStatus status) {
    switch (status) {
      case ItemStatus.pending:
        return 'pending';
      case ItemStatus.ordered:
        return 'ordered';
      case ItemStatus.inTransit:
        return 'in_transit';
      case ItemStatus.delivered:
        return 'delivered';
      case ItemStatus.cancelled:
        return 'cancelled';
    }
  }

  static List<TrackingUpdate> _parseTrackingUpdates(dynamic updates) {
    if (updates == null || updates is! List) return [];
    return updates
        .map((u) => TrackingUpdateModel.fromJson(u as Map<String, dynamic>))
        .toList();
  }
}
