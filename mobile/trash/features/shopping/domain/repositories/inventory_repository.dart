import 'package:dartz/dartz.dart';
import '../../../../core/error/failures.dart';
import '../entities/inventory_item.dart';
import '../entities/shopping_item.dart';

/// 库存管理仓库接口
abstract class InventoryRepository {
  // ========== 库存操作 ==========

  /// 获取库存列表
  Future<Either<Failure, List<InventoryItem>>> getInventoryList({
    ItemCategory? category,
    bool lowStockOnly = false,
    int page = 1,
    int pageSize = 50,
  });

  /// 获取单个库存商品
  Future<Either<Failure, InventoryItem>> getInventoryItemById(String itemId);

  /// 获取库存不足的商品
  Future<Either<Failure, List<InventoryItem>>> getLowStockItems();

  /// 获取补货建议
  Future<Either<Failure, List<InventoryItem>>> getReplenishmentSuggestions({
    int advanceDays = 7,
  });

  /// 创建库存商品
  Future<Either<Failure, InventoryItem>> createInventoryItem({
    required String productName,
    ItemCategory? category,
    required double currentQuantity,
    required double minThreshold,
    String? unit,
    String? storageLocation,
    DateTime? expiryDate,
  });

  /// 更新库存商品
  Future<Either<Failure, InventoryItem>> updateInventoryItem({
    required String itemId,
    String? productName,
    ItemCategory? category,
    double? currentQuantity,
    double? minThreshold,
    String? unit,
    String? storageLocation,
    DateTime? expiryDate,
  });

  /// 调整库存数量
  Future<Either<Failure, InventoryItem>> adjustInventoryQuantity({
    required String itemId,
    required double quantityChange, // 正数增加，负数减少
  });

  /// 删除库存商品
  Future<Either<Failure, void>> deleteInventoryItem(String itemId);

  /// 记录购买（更新库存）
  Future<Either<Failure, InventoryItem>> recordPurchase({
    required String productName,
    required double quantity,
    String? unit,
    double? price,
    String? merchant,
  });

  // ========== 统计和分析 ==========

  /// 获取库存统计摘要
  Future<Either<Failure, InventorySummary>> getInventorySummary();
}

/// 库存统计摘要
class InventorySummary {
  final int totalItems;
  final int lowStockCount;
  final int expiringCount;
  final int expiredCount;
  final List<InventoryItem> topLowStockItems;

  const InventorySummary({
    required this.totalItems,
    required this.lowStockCount,
    required this.expiringCount,
    required this.expiredCount,
    this.topLowStockItems = const [],
  });
}
