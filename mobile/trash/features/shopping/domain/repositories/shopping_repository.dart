import 'package:dartz/dartz.dart';
import '../../../../core/error/failures.dart';
import '../entities/shopping_list.dart';
import '../entities/shopping_item.dart';
import '../entities/product_recommendation.dart';
import '../entities/bundle_opportunity.dart';

/// 购物清单仓库接口
abstract class ShoppingRepository {
  // ========== 购物清单操作 ==========

  /// 获取购物清单列表
  Future<Either<Failure, List<ShoppingList>>> getShoppingLists({
    ListStatus? statusFilter,
    ListType? listTypeFilter,
    int page = 1,
    int pageSize = 20,
  });

  /// 获取单个购物清单详情
  Future<Either<Failure, ShoppingList>> getShoppingListById(String listId);

  /// 创建购物清单
  Future<Either<Failure, ShoppingList>> createShoppingList({
    required String listName,
    required ListType listType,
    DateTime? dueDate,
  });

  /// 更新购物清单
  Future<Either<Failure, ShoppingList>> updateShoppingList({
    required String listId,
    String? listName,
    ListType? listType,
    ListStatus? status,
    DateTime? dueDate,
  });

  /// 完成购物清单
  Future<Either<Failure, ShoppingList>> completeShoppingList(String listId);

  /// 删除购物清单
  Future<Either<Failure, void>> deleteShoppingList(String listId);

  // ========== 购物商品操作 ==========

  /// 获取清单内的商品列表
  Future<Either<Failure, List<ShoppingItem>>> getListItems({
    required String listId,
    String? category,
    bool? purchased,
  });

  /// 添加商品到清单
  Future<Either<Failure, ShoppingItem>> addItem({
    required String listId,
    required String productName,
    String? category,
    double quantity = 1,
    String? unit,
    int priority = 3,
    double? estimatedPrice,
    String? notes,
  });

  /// 通过自然语言添加商品（AI解析）
  Future<Either<Failure, ShoppingItem>> addItemFromConversation({
    required String listId,
    required String conversationText,
  });

  /// 更新商品信息
  Future<Either<Failure, ShoppingItem>> updateItem({
    required String listId,
    required String itemId,
    String? productName,
    String? category,
    double? quantity,
    String? unit,
    int? priority,
    double? estimatedPrice,
    String? notes,
  });

  /// 标记商品已购买
  Future<Either<Failure, ShoppingItem>> markItemPurchased({
    required String listId,
    required String itemId,
    double? actualPrice,
    String? merchant,
  });

  /// 取消标记商品已购买
  Future<Either<Failure, ShoppingItem>> unmarkItemPurchased({
    required String listId,
    required String itemId,
  });

  /// 删除商品
  Future<Either<Failure, void>> deleteItem({
    required String listId,
    required String itemId,
  });

  /// 更新商品状态（新增）
  Future<Either<Failure, ShoppingItem>> updateItemStatus({
    required String listId,
    required String itemId,
    required ItemStatus itemStatus,
    String? trackingNumber,
    DateTime? expectedDeliveryDate,
  });

  /// 取消商品订单（新增）
  Future<Either<Failure, ShoppingItem>> cancelItemOrder({
    required String listId,
    required String itemId,
  });

  // ========== 推荐功能 ==========

  /// 获取商品推荐
  Future<Either<Failure, List<ProductRecommendation>>> getProductRecommendations({
    int limit = 10,
  });

  /// 获取凑单建议
  Future<Either<Failure, List<BundleOpportunity>>> getBundleRecommendations({
    required String listId,
  });

  /// 获取季节性推荐
  Future<Either<Failure, List<ProductRecommendation>>> getSeasonalRecommendations();
}
