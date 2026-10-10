import '../../domain/entities/inventory_item.dart';
import '../../domain/entities/shopping_item.dart';

class InventoryItemModel extends InventoryItem {
  const InventoryItemModel({
    required super.id,
    required super.familyId,
    required super.productName,
    super.category,
    required super.currentQuantity,
    required super.minThreshold,
    super.unit,
    super.storageLocation,
    super.expiryDate,
    super.lastReplenishmentDate,
    super.predictedDepletionDate,
    super.dailyConsumptionRate,
    super.purchaseFrequencyDays,
    required super.createdAt,
    required super.updatedAt,
  });

  factory InventoryItemModel.fromJson(Map<String, dynamic> json) {
    return InventoryItemModel(
      id: json['id']?.toString() ?? json['inventory_id']?.toString() ?? '',
      familyId: json['family_id']?.toString() ?? '',
      productName: json['product_name'] ?? '',
      category: _parseCategory(json['category']),
      currentQuantity: (json['current_quantity'] ?? 0).toDouble(),
      minThreshold: (json['min_threshold'] ?? 0).toDouble(),
      unit: json['unit'],
      storageLocation: json['storage_location'],
      expiryDate: json['expiry_date'] != null ? DateTime.tryParse(json['expiry_date']) : null,
      lastReplenishmentDate: json['last_replenishment_date'] != null
          ? DateTime.tryParse(json['last_replenishment_date']) : null,
      predictedDepletionDate: json['predicted_depletion_date'] != null
          ? DateTime.tryParse(json['predicted_depletion_date']) : null,
      dailyConsumptionRate: json['daily_consumption_rate']?.toDouble(),
      purchaseFrequencyDays: json['purchase_frequency_days'],
      createdAt: DateTime.tryParse(json['created_at'] ?? '') ?? DateTime.now(),
      updatedAt: DateTime.tryParse(json['updated_at'] ?? '') ?? DateTime.now(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'family_id': familyId,
      'product_name': productName,
      'category': category != null ? _categoryToString(category!) : null,
      'current_quantity': currentQuantity,
      'min_threshold': minThreshold,
      'unit': unit,
      'storage_location': storageLocation,
      'expiry_date': expiryDate?.toIso8601String(),
      'last_replenishment_date': lastReplenishmentDate?.toIso8601String(),
      'predicted_depletion_date': predictedDepletionDate?.toIso8601String(),
      'daily_consumption_rate': dailyConsumptionRate,
      'purchase_frequency_days': purchaseFrequencyDays,
      'created_at': createdAt.toIso8601String(),
      'updated_at': updatedAt.toIso8601String(),
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
}
