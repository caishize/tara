import '../../../../core/network/api_client.dart';
import '../models/inventory_item_model.dart';
import '../../domain/entities/shopping_item.dart';

/// 库存管理远程数据源
class InventoryRemoteDataSource {
  final ApiClient _apiClient;

  InventoryRemoteDataSource(this._apiClient);

  /// 获取库存列表
  Future<List<InventoryItemModel>> getInventoryList({
    String? category,
    bool lowStockOnly = false,
    int page = 1,
    int pageSize = 50,
  }) async {
    final queryParams = <String, dynamic>{
      'page': page,
      'page_size': pageSize,
      if (lowStockOnly) 'low_stock_only': lowStockOnly,
    };
    if (category != null) queryParams['category'] = category;

    final response = await _apiClient.get<dynamic>(
      '/shopping/inventory/',
      queryParameters: queryParams,
    );

    // Handle both List and paginated Map responses
    final List<dynamic> items;
    if (response is List) {
      items = response;
    } else if (response is Map<String, dynamic>) {
      items = response['items'] ?? response['results'] ?? [];
    } else {
      items = [];
    }

    return items.map((json) => InventoryItemModel.fromJson(json as Map<String, dynamic>)).toList();
  }

  /// 获取单个库存商品
  Future<InventoryItemModel> getInventoryItemById(String itemId) async {
    final response = await _apiClient.get<Map<String, dynamic>>(
      '/shopping/inventory/$itemId/',
    );
    return InventoryItemModel.fromJson(response);
  }

  /// 获取库存不足的商品
  Future<List<InventoryItemModel>> getLowStockItems() async {
    final response = await _apiClient.get<dynamic>(
      '/shopping/inventory/low-stock/',
    );

    final List<dynamic> items;
    if (response is List) {
      items = response;
    } else if (response is Map<String, dynamic>) {
      items = response['items'] ?? response['results'] ?? [];
    } else {
      items = [];
    }

    return items.map((json) => InventoryItemModel.fromJson(json as Map<String, dynamic>)).toList();
  }

  /// 获取补货建议
  Future<List<InventoryItemModel>> getReplenishmentSuggestions({
    int advanceDays = 7,
  }) async {
    final response = await _apiClient.get<dynamic>(
      '/shopping/inventory/replenishment-suggestions/',
      queryParameters: {'advance_days': advanceDays},
    );

    final List<dynamic> items;
    if (response is List) {
      items = response;
    } else if (response is Map<String, dynamic>) {
      items = response['items'] ?? response['results'] ?? [];
    } else {
      items = [];
    }

    return items.map((json) => InventoryItemModel.fromJson(json as Map<String, dynamic>)).toList();
  }

  /// 创建库存商品
  Future<InventoryItemModel> createInventoryItem({
    required String productName,
    String? category,
    required double currentQuantity,
    required double minThreshold,
    String? unit,
    String? storageLocation,
    DateTime? expiryDate,
  }) async {
    final response = await _apiClient.post<Map<String, dynamic>>(
      '/shopping/inventory/',
      data: {
        'product_name': productName,
        if (category != null) 'category': category,
        'current_quantity': currentQuantity,
        'min_threshold': minThreshold,
        if (unit != null) 'unit': unit,
        if (storageLocation != null) 'storage_location': storageLocation,
        if (expiryDate != null) 'expiry_date': expiryDate.toIso8601String(),
      },
    );
    return InventoryItemModel.fromJson(response);
  }

  /// 更新库存商品
  Future<InventoryItemModel> updateInventoryItem({
    required String itemId,
    String? productName,
    String? category,
    double? currentQuantity,
    double? minThreshold,
    String? unit,
    String? storageLocation,
    DateTime? expiryDate,
  }) async {
    final data = <String, dynamic>{};
    if (productName != null) data['product_name'] = productName;
    if (category != null) data['category'] = category;
    if (currentQuantity != null) data['current_quantity'] = currentQuantity;
    if (minThreshold != null) data['min_threshold'] = minThreshold;
    if (unit != null) data['unit'] = unit;
    if (storageLocation != null) data['storage_location'] = storageLocation;
    if (expiryDate != null) data['expiry_date'] = expiryDate.toIso8601String();

    final response = await _apiClient.patch<Map<String, dynamic>>(
      '/shopping/inventory/$itemId/',
      data: data,
    );
    return InventoryItemModel.fromJson(response);
  }

  /// 调整库存数量
  Future<InventoryItemModel> adjustInventoryQuantity({
    required String itemId,
    required double quantityChange,
  }) async {
    final response = await _apiClient.post<Map<String, dynamic>>(
      '/shopping/inventory/$itemId/adjust/',
      data: {
        'quantity_change': quantityChange,
      },
    );
    return InventoryItemModel.fromJson(response);
  }

  /// 删除库存商品
  Future<void> deleteInventoryItem(String itemId) async {
    await _apiClient.delete<void>('/shopping/inventory/$itemId/');
  }

  /// 记录购买
  Future<InventoryItemModel> recordPurchase({
    required String productName,
    required double quantity,
    String? unit,
    double? price,
    String? merchant,
  }) async {
    final response = await _apiClient.post<Map<String, dynamic>>(
      '/shopping/inventory/purchase/',
      data: {
        'product_name': productName,
        'quantity': quantity,
        if (unit != null) 'unit': unit,
        if (price != null) 'price': price,
        if (merchant != null) 'merchant': merchant,
      },
    );
    return InventoryItemModel.fromJson(response);
  }

  /// 获取库存统计摘要
  Future<Map<String, dynamic>> getInventorySummary() async {
    final response = await _apiClient.get<Map<String, dynamic>>(
      '/shopping/inventory/summary/',
    );
    return response;
  }
}

// ========== Helper Functions ==========

String itemCategoryToString(ItemCategory category) {
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
