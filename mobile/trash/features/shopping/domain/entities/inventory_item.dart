import 'package:equatable/equatable.dart';
import 'shopping_item.dart';

/// 库存状态
enum StockStatus {
  adequate,   // 充足
  low,        // 偏低
  critical,   // 紧缺
}

/// 家庭库存商品实体
class InventoryItem extends Equatable {
  final String id;
  final String familyId;
  final String productName;
  final ItemCategory? category;
  final double currentQuantity;
  final double minThreshold;
  final String? unit;
  final String? storageLocation;
  final DateTime? expiryDate;
  final DateTime? lastReplenishmentDate;
  final DateTime? predictedDepletionDate;
  final double? dailyConsumptionRate;
  final int? purchaseFrequencyDays;
  final DateTime createdAt;
  final DateTime updatedAt;

  const InventoryItem({
    required this.id,
    required this.familyId,
    required this.productName,
    this.category,
    required this.currentQuantity,
    required this.minThreshold,
    this.unit,
    this.storageLocation,
    this.expiryDate,
    this.lastReplenishmentDate,
    this.predictedDepletionDate,
    this.dailyConsumptionRate,
    this.purchaseFrequencyDays,
    required this.createdAt,
    required this.updatedAt,
  });

  /// 库存状态
  StockStatus get stockStatus {
    if (currentQuantity <= minThreshold * 0.5) {
      return StockStatus.critical;
    } else if (currentQuantity <= minThreshold) {
      return StockStatus.low;
    }
    return StockStatus.adequate;
  }

  /// 是否需要补货
  bool get needsReplenishment => currentQuantity <= minThreshold;

  /// 库存百分比（相对于最低阈值的2倍）
  double get stockPercentage {
    final maxStock = minThreshold * 2;
    return (currentQuantity / maxStock).clamp(0.0, 1.0);
  }

  /// 距离过期的天数
  int? get daysUntilExpiry {
    if (expiryDate == null) return null;
    return expiryDate!.difference(DateTime.now()).inDays;
  }

  /// 是否即将过期（7天内）
  bool get isExpiringSoon {
    final days = daysUntilExpiry;
    return days != null && days <= 7 && days > 0;
  }

  /// 是否已过期
  bool get isExpired {
    final days = daysUntilExpiry;
    return days != null && days <= 0;
  }

  /// 距离预计耗尽的天数
  int? get daysUntilDepletion {
    if (predictedDepletionDate == null) return null;
    return predictedDepletionDate!.difference(DateTime.now()).inDays;
  }

  /// 获取状态显示名称
  String get stockStatusName {
    switch (stockStatus) {
      case StockStatus.adequate:
        return '充足';
      case StockStatus.low:
        return '偏低';
      case StockStatus.critical:
        return '紧缺';
    }
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

  /// 显示数量和单位
  String get quantityDisplay {
    if (unit != null && unit!.isNotEmpty) {
      return '$currentQuantity $unit';
    }
    return currentQuantity.toString();
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
        return '🦐';
      case ItemCategory.vegetable:
        return '🥬';
      case ItemCategory.fruit:
        return '🍎';
      case ItemCategory.grain:
        return '🌾';
      case ItemCategory.snack:
        return '🍪';
      case ItemCategory.beverage:
        return '🧃';
      case ItemCategory.household:
        return '🧹';
      case ItemCategory.personal:
        return '🧴';
      case ItemCategory.baby:
        return '🍼';
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

  InventoryItem copyWith({
    String? id,
    String? familyId,
    String? productName,
    ItemCategory? category,
    double? currentQuantity,
    double? minThreshold,
    String? unit,
    String? storageLocation,
    DateTime? expiryDate,
    DateTime? lastReplenishmentDate,
    DateTime? predictedDepletionDate,
    double? dailyConsumptionRate,
    int? purchaseFrequencyDays,
    DateTime? createdAt,
    DateTime? updatedAt,
  }) {
    return InventoryItem(
      id: id ?? this.id,
      familyId: familyId ?? this.familyId,
      productName: productName ?? this.productName,
      category: category ?? this.category,
      currentQuantity: currentQuantity ?? this.currentQuantity,
      minThreshold: minThreshold ?? this.minThreshold,
      unit: unit ?? this.unit,
      storageLocation: storageLocation ?? this.storageLocation,
      expiryDate: expiryDate ?? this.expiryDate,
      lastReplenishmentDate: lastReplenishmentDate ?? this.lastReplenishmentDate,
      predictedDepletionDate: predictedDepletionDate ?? this.predictedDepletionDate,
      dailyConsumptionRate: dailyConsumptionRate ?? this.dailyConsumptionRate,
      purchaseFrequencyDays: purchaseFrequencyDays ?? this.purchaseFrequencyDays,
      createdAt: createdAt ?? this.createdAt,
      updatedAt: updatedAt ?? this.updatedAt,
    );
  }

  @override
  List<Object?> get props => [
    id, familyId, productName, category, currentQuantity, minThreshold,
    unit, storageLocation, expiryDate, lastReplenishmentDate,
    predictedDepletionDate, dailyConsumptionRate, purchaseFrequencyDays,
    createdAt, updatedAt,
  ];
}
