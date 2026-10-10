import '../../../../core/network/api_client.dart';
import '../models/shopping_list_model.dart';
import '../models/shopping_item_model.dart';
import '../models/product_recommendation_model.dart';
import '../../domain/entities/shopping_list.dart';

/// 购物清单远程数据源
class ShoppingRemoteDataSource {
  final ApiClient _apiClient;

  ShoppingRemoteDataSource(this._apiClient);

  // ========== 购物清单操作 ==========

  /// 获取购物清单列表
  Future<List<ShoppingListModel>> getShoppingLists({
    String? statusFilter,
    String? listTypeFilter,
    int page = 1,
    int pageSize = 20,
  }) async {
    final queryParams = <String, dynamic>{
      'page': page,
      'page_size': pageSize,
    };
    if (statusFilter != null) queryParams['status'] = statusFilter;
    if (listTypeFilter != null) queryParams['list_type'] = listTypeFilter;

    final response = await _apiClient.get<dynamic>(
      '/shopping/shopping-lists',
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

    return items.map((json) => ShoppingListModel.fromJson(json as Map<String, dynamic>)).toList();
  }

  /// 获取单个购物清单
  Future<ShoppingListModel> getShoppingListById(String listId) async {
    final response = await _apiClient.get<Map<String, dynamic>>(
      '/shopping/shopping-lists/$listId',
    );
    return ShoppingListModel.fromJson(response);
  }

  /// 创建购物清单
  Future<ShoppingListModel> createShoppingList({
    required String listName,
    required String listType,
    DateTime? dueDate,
  }) async {
    final response = await _apiClient.post<Map<String, dynamic>>(
      '/shopping/shopping-lists',
      data: {
        'list_name': listName,
        'list_type': listType,
        if (dueDate != null) 'due_date': dueDate.toIso8601String(),
      },
    );
    return ShoppingListModel.fromJson(response);
  }

  /// 更新购物清单
  Future<ShoppingListModel> updateShoppingList({
    required String listId,
    String? listName,
    String? listType,
    String? status,
    DateTime? dueDate,
  }) async {
    final data = <String, dynamic>{};
    if (listName != null) data['list_name'] = listName;
    if (listType != null) data['list_type'] = listType;
    if (status != null) data['status'] = status;
    if (dueDate != null) data['due_date'] = dueDate.toIso8601String();

    final response = await _apiClient.patch<Map<String, dynamic>>(
      '/shopping/shopping-lists/$listId',
      data: data,
    );
    return ShoppingListModel.fromJson(response);
  }

  /// 完成购物清单
  Future<ShoppingListModel> completeShoppingList(String listId) async {
    final response = await _apiClient.post<Map<String, dynamic>>(
      '/shopping/shopping-lists/$listId/complete',
    );
    return ShoppingListModel.fromJson(response);
  }

  /// 删除购物清单
  Future<void> deleteShoppingList(String listId) async {
    await _apiClient.delete<void>('/shopping/shopping-lists/$listId');
  }

  // ========== 购物商品操作 ==========

  /// 获取清单内的商品列表
  Future<List<ShoppingItemModel>> getListItems({
    required String listId,
    String? category,
    bool? purchased,
  }) async {
    final queryParams = <String, dynamic>{};
    if (category != null) queryParams['category'] = category;
    if (purchased != null) queryParams['purchased'] = purchased;

    final response = await _apiClient.get<dynamic>(
      '/shopping/shopping-lists/$listId/items',
      queryParameters: queryParams.isEmpty ? null : queryParams,
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

    return items.map((json) => ShoppingItemModel.fromJson(json as Map<String, dynamic>)).toList();
  }

  /// 添加商品到清单
  Future<ShoppingItemModel> addItem({
    required String listId,
    required String productName,
    String? category,
    double quantity = 1,
    String? unit,
    int priority = 3,
    double? estimatedPrice,
    String? notes,
  }) async {
    final response = await _apiClient.post<Map<String, dynamic>>(
      '/shopping/shopping-lists/$listId/items',
      data: {
        'product_name': productName,
        if (category != null) 'category': category,
        'quantity': quantity,
        if (unit != null) 'unit': unit,
        'priority': priority,
        if (estimatedPrice != null) 'estimated_price': estimatedPrice,
        if (notes != null) 'notes': notes,
      },
    );
    return ShoppingItemModel.fromJson(response);
  }

  /// 通过自然语言添加商品
  Future<ShoppingItemModel> addItemFromConversation({
    required String listId,
    required String conversationText,
  }) async {
    final response = await _apiClient.post<Map<String, dynamic>>(
      '/shopping/shopping-lists/$listId/items/conversational',
      data: {
        'conversation_text': conversationText,
      },
    );
    return ShoppingItemModel.fromJson(response);
  }

  /// 更新商品信息
  Future<ShoppingItemModel> updateItem({
    required String listId,
    required String itemId,
    String? productName,
    String? category,
    double? quantity,
    String? unit,
    int? priority,
    double? estimatedPrice,
    String? notes,
  }) async {
    final data = <String, dynamic>{};
    if (productName != null) data['product_name'] = productName;
    if (category != null) data['category'] = category;
    if (quantity != null) data['quantity'] = quantity;
    if (unit != null) data['unit'] = unit;
    if (priority != null) data['priority'] = priority;
    if (estimatedPrice != null) data['estimated_price'] = estimatedPrice;
    if (notes != null) data['notes'] = notes;

    final response = await _apiClient.patch<Map<String, dynamic>>(
      '/shopping/shopping-lists/$listId/items/$itemId',
      data: data,
    );
    return ShoppingItemModel.fromJson(response);
  }

  /// 标记商品已购买
  Future<ShoppingItemModel> markItemPurchased({
    required String listId,
    required String itemId,
    double? actualPrice,
    String? merchant,
  }) async {
    final response = await _apiClient.post<Map<String, dynamic>>(
      '/shopping/shopping-lists/$listId/items/$itemId/purchase',
      data: {
        if (actualPrice != null) 'actual_price': actualPrice,
        if (merchant != null) 'merchant': merchant,
      },
    );
    return ShoppingItemModel.fromJson(response);
  }

  /// 删除商品
  Future<void> deleteItem({
    required String listId,
    required String itemId,
  }) async {
    await _apiClient.delete<void>('/shopping/shopping-lists/$listId/items/$itemId');
  }

  /// 更新商品状态（新增）
  Future<ShoppingItemModel> updateItemStatus({
    required String listId,
    required String itemId,
    required String itemStatus,
    String? trackingNumber,
    DateTime? expectedDeliveryDate,
  }) async {
    final response = await _apiClient.post<Map<String, dynamic>>(
      '/shopping/shopping-lists/$listId/items/$itemId/status',
      data: {
        'item_status': itemStatus,
        if (trackingNumber != null) 'tracking_number': trackingNumber,
        if (expectedDeliveryDate != null)
          'expected_delivery_date': expectedDeliveryDate.toIso8601String().split('T')[0],
      },
    );
    return ShoppingItemModel.fromJson(response);
  }

  /// 取消商品订单（新增）
  Future<ShoppingItemModel> cancelItemOrder({
    required String listId,
    required String itemId,
  }) async {
    final response = await _apiClient.post<Map<String, dynamic>>(
      '/shopping/shopping-lists/$listId/items/$itemId/cancel',
    );
    return ShoppingItemModel.fromJson(response);
  }

  // ========== 推荐功能 ==========

  /// 获取商品推荐
  Future<List<ProductRecommendationModel>> getProductRecommendations({
    int limit = 10,
  }) async {
    final response = await _apiClient.get<dynamic>(
      '/shopping/recommendations/products',
      queryParameters: {'limit': limit},
    );

    // Handle both List and paginated Map responses
    final List<dynamic> items;
    if (response is List) {
      items = response;
    } else if (response is Map<String, dynamic>) {
      items = response['items'] ?? response['results'] ?? response['recommendations'] ?? [];
    } else {
      items = [];
    }

    return items.map((json) => ProductRecommendationModel.fromJson(json as Map<String, dynamic>)).toList();
  }

  /// 获取凑单建议
  Future<List<BundleOpportunityModel>> getBundleRecommendations({
    required String listId,
  }) async {
    final response = await _apiClient.get<Map<String, dynamic>>(
      '/shopping/recommendations/bundle',
      queryParameters: {'list_id': listId},
    );

    // API可能返回单个对象或列表
    if (response.containsKey('opportunities')) {
      final opportunities = response['opportunities'] as List<dynamic>? ?? [];
      return opportunities.map((json) => BundleOpportunityModel.fromJson(json as Map<String, dynamic>)).toList();
    } else if (response.containsKey('coupon_name')) {
      return [BundleOpportunityModel.fromJson(response)];
    }
    return [];
  }

  /// 获取季节性推荐
  Future<List<ProductRecommendationModel>> getSeasonalRecommendations() async {
    final response = await _apiClient.get<dynamic>(
      '/shopping/recommendations/seasonal',
    );

    // Handle both List and paginated Map responses
    final List<dynamic> items;
    if (response is List) {
      items = response;
    } else if (response is Map<String, dynamic>) {
      items = response['items'] ?? response['results'] ?? response['recommendations'] ?? [];
    } else {
      items = [];
    }

    return items.map((json) => ProductRecommendationModel.fromJson(json as Map<String, dynamic>)).toList();
  }
}

// ========== Helper Functions ==========

String listTypeToString(ListType type) {
  switch (type) {
    case ListType.regular:
      return 'regular';
    case ListType.replenishment:
      return 'replenishment';
    case ListType.seasonal:
      return 'seasonal';
    case ListType.bulk:
      return 'bulk';
    case ListType.urgent:
      return 'urgent';
  }
}

String listStatusToString(ListStatus status) {
  switch (status) {
    case ListStatus.active:
      return 'active';
    case ListStatus.inProgress:
      return 'in_progress';
    case ListStatus.completed:
      return 'completed';
    case ListStatus.archived:
      return 'archived';
  }
}
