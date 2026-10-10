import 'package:dartz/dartz.dart';
import '../../../../core/error/exceptions.dart';
import '../../../../core/error/failures.dart';
import '../../domain/entities/shopping_list.dart';
import '../../domain/entities/shopping_item.dart';
import '../../domain/entities/product_recommendation.dart';
import '../../domain/entities/bundle_opportunity.dart';
import '../../domain/repositories/shopping_repository.dart';
import '../datasources/shopping_remote_datasource.dart';

/// 购物清单仓库实现
class ShoppingRepositoryImpl implements ShoppingRepository {
  final ShoppingRemoteDataSource remoteDataSource;

  ShoppingRepositoryImpl({required this.remoteDataSource});

  // ========== 购物清单操作 ==========

  @override
  Future<Either<Failure, List<ShoppingList>>> getShoppingLists({
    ListStatus? statusFilter,
    ListType? listTypeFilter,
    int page = 1,
    int pageSize = 20,
  }) async {
    try {
      final lists = await remoteDataSource.getShoppingLists(
        statusFilter: statusFilter != null ? listStatusToString(statusFilter) : null,
        listTypeFilter: listTypeFilter != null ? listTypeToString(listTypeFilter) : null,
        page: page,
        pageSize: pageSize,
      );
      return Right(lists);
    } on NetworkException catch (e) {
      return Left(NetworkFailure(e.message));
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message));
    } on UnauthorizedException catch (e) {
      return Left(AuthFailure(e.message));
    } catch (e) {
      return Left(UnknownFailure(e.toString()));
    }
  }

  @override
  Future<Either<Failure, ShoppingList>> getShoppingListById(String listId) async {
    try {
      final list = await remoteDataSource.getShoppingListById(listId);
      return Right(list);
    } on NetworkException catch (e) {
      return Left(NetworkFailure(e.message));
    } on NotFoundException catch (e) {
      return Left(NotFoundFailure(e.message));
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message));
    } catch (e) {
      return Left(UnknownFailure(e.toString()));
    }
  }

  @override
  Future<Either<Failure, ShoppingList>> createShoppingList({
    required String listName,
    required ListType listType,
    DateTime? dueDate,
  }) async {
    try {
      final list = await remoteDataSource.createShoppingList(
        listName: listName,
        listType: listTypeToString(listType),
        dueDate: dueDate,
      );
      return Right(list);
    } on NetworkException catch (e) {
      return Left(NetworkFailure(e.message));
    } on ValidationException catch (e) {
      return Left(ValidationFailure(e.message, e.errors));
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message));
    } catch (e) {
      return Left(UnknownFailure(e.toString()));
    }
  }

  @override
  Future<Either<Failure, ShoppingList>> updateShoppingList({
    required String listId,
    String? listName,
    ListType? listType,
    ListStatus? status,
    DateTime? dueDate,
  }) async {
    try {
      final list = await remoteDataSource.updateShoppingList(
        listId: listId,
        listName: listName,
        listType: listType != null ? listTypeToString(listType) : null,
        status: status != null ? listStatusToString(status) : null,
        dueDate: dueDate,
      );
      return Right(list);
    } on NetworkException catch (e) {
      return Left(NetworkFailure(e.message));
    } on NotFoundException catch (e) {
      return Left(NotFoundFailure(e.message));
    } on ValidationException catch (e) {
      return Left(ValidationFailure(e.message, e.errors));
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message));
    } catch (e) {
      return Left(UnknownFailure(e.toString()));
    }
  }

  @override
  Future<Either<Failure, ShoppingList>> completeShoppingList(String listId) async {
    try {
      final list = await remoteDataSource.completeShoppingList(listId);
      return Right(list);
    } on NetworkException catch (e) {
      return Left(NetworkFailure(e.message));
    } on NotFoundException catch (e) {
      return Left(NotFoundFailure(e.message));
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message));
    } catch (e) {
      return Left(UnknownFailure(e.toString()));
    }
  }

  @override
  Future<Either<Failure, void>> deleteShoppingList(String listId) async {
    try {
      await remoteDataSource.deleteShoppingList(listId);
      return const Right(null);
    } on NetworkException catch (e) {
      return Left(NetworkFailure(e.message));
    } on NotFoundException catch (e) {
      return Left(NotFoundFailure(e.message));
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message));
    } catch (e) {
      return Left(UnknownFailure(e.toString()));
    }
  }

  // ========== 购物商品操作 ==========

  @override
  Future<Either<Failure, List<ShoppingItem>>> getListItems({
    required String listId,
    String? category,
    bool? purchased,
  }) async {
    try {
      final items = await remoteDataSource.getListItems(
        listId: listId,
        category: category,
        purchased: purchased,
      );
      return Right(items);
    } on NetworkException catch (e) {
      return Left(NetworkFailure(e.message));
    } on NotFoundException catch (e) {
      return Left(NotFoundFailure(e.message));
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message));
    } catch (e) {
      return Left(UnknownFailure(e.toString()));
    }
  }

  @override
  Future<Either<Failure, ShoppingItem>> addItem({
    required String listId,
    required String productName,
    String? category,
    double quantity = 1,
    String? unit,
    int priority = 3,
    double? estimatedPrice,
    String? notes,
  }) async {
    try {
      final item = await remoteDataSource.addItem(
        listId: listId,
        productName: productName,
        category: category,
        quantity: quantity,
        unit: unit,
        priority: priority,
        estimatedPrice: estimatedPrice,
        notes: notes,
      );
      return Right(item);
    } on NetworkException catch (e) {
      return Left(NetworkFailure(e.message));
    } on ValidationException catch (e) {
      return Left(ValidationFailure(e.message, e.errors));
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message));
    } catch (e) {
      return Left(UnknownFailure(e.toString()));
    }
  }

  @override
  Future<Either<Failure, ShoppingItem>> addItemFromConversation({
    required String listId,
    required String conversationText,
  }) async {
    try {
      final item = await remoteDataSource.addItemFromConversation(
        listId: listId,
        conversationText: conversationText,
      );
      return Right(item);
    } on NetworkException catch (e) {
      return Left(NetworkFailure(e.message));
    } on ValidationException catch (e) {
      return Left(ValidationFailure(e.message, e.errors));
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message));
    } catch (e) {
      return Left(UnknownFailure(e.toString()));
    }
  }

  @override
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
  }) async {
    try {
      final item = await remoteDataSource.updateItem(
        listId: listId,
        itemId: itemId,
        productName: productName,
        category: category,
        quantity: quantity,
        unit: unit,
        priority: priority,
        estimatedPrice: estimatedPrice,
        notes: notes,
      );
      return Right(item);
    } on NetworkException catch (e) {
      return Left(NetworkFailure(e.message));
    } on NotFoundException catch (e) {
      return Left(NotFoundFailure(e.message));
    } on ValidationException catch (e) {
      return Left(ValidationFailure(e.message, e.errors));
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message));
    } catch (e) {
      return Left(UnknownFailure(e.toString()));
    }
  }

  @override
  Future<Either<Failure, ShoppingItem>> markItemPurchased({
    required String listId,
    required String itemId,
    double? actualPrice,
    String? merchant,
  }) async {
    try {
      final item = await remoteDataSource.markItemPurchased(
        listId: listId,
        itemId: itemId,
        actualPrice: actualPrice,
        merchant: merchant,
      );
      return Right(item);
    } on NetworkException catch (e) {
      return Left(NetworkFailure(e.message));
    } on NotFoundException catch (e) {
      return Left(NotFoundFailure(e.message));
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message));
    } catch (e) {
      return Left(UnknownFailure(e.toString()));
    }
  }

  @override
  Future<Either<Failure, ShoppingItem>> unmarkItemPurchased({
    required String listId,
    required String itemId,
  }) async {
    try {
      final item = await remoteDataSource.updateItem(
        listId: listId,
        itemId: itemId,
      );
      return Right(item);
    } on NetworkException catch (e) {
      return Left(NetworkFailure(e.message));
    } on NotFoundException catch (e) {
      return Left(NotFoundFailure(e.message));
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message));
    } catch (e) {
      return Left(UnknownFailure(e.toString()));
    }
  }

  @override
  Future<Either<Failure, void>> deleteItem({
    required String listId,
    required String itemId,
  }) async {
    try {
      await remoteDataSource.deleteItem(listId: listId, itemId: itemId);
      return const Right(null);
    } on NetworkException catch (e) {
      return Left(NetworkFailure(e.message));
    } on NotFoundException catch (e) {
      return Left(NotFoundFailure(e.message));
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message));
    } catch (e) {
      return Left(UnknownFailure(e.toString()));
    }
  }

  @override
  Future<Either<Failure, ShoppingItem>> updateItemStatus({
    required String listId,
    required String itemId,
    required ItemStatus itemStatus,
    String? trackingNumber,
    DateTime? expectedDeliveryDate,
  }) async {
    try {
      final item = await remoteDataSource.updateItemStatus(
        listId: listId,
        itemId: itemId,
        itemStatus: itemStatus.name,
        trackingNumber: trackingNumber,
        expectedDeliveryDate: expectedDeliveryDate,
      );
      return Right(item);
    } on NetworkException catch (e) {
      return Left(NetworkFailure(e.message));
    } on NotFoundException catch (e) {
      return Left(NotFoundFailure(e.message));
    } on ValidationException catch (e) {
      return Left(ValidationFailure(e.message, e.errors));
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message));
    } catch (e) {
      return Left(UnknownFailure(e.toString()));
    }
  }

  @override
  Future<Either<Failure, ShoppingItem>> cancelItemOrder({
    required String listId,
    required String itemId,
  }) async {
    try {
      final item = await remoteDataSource.cancelItemOrder(
        listId: listId,
        itemId: itemId,
      );
      return Right(item);
    } on NetworkException catch (e) {
      return Left(NetworkFailure(e.message));
    } on NotFoundException catch (e) {
      return Left(NotFoundFailure(e.message));
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message));
    } catch (e) {
      return Left(UnknownFailure(e.toString()));
    }
  }

  // ========== 推荐功能 ==========

  @override
  Future<Either<Failure, List<ProductRecommendation>>> getProductRecommendations({
    int limit = 10,
  }) async {
    try {
      final recommendations = await remoteDataSource.getProductRecommendations(
        limit: limit,
      );
      return Right(recommendations);
    } on NetworkException catch (e) {
      return Left(NetworkFailure(e.message));
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message));
    } catch (e) {
      return Left(UnknownFailure(e.toString()));
    }
  }

  @override
  Future<Either<Failure, List<BundleOpportunity>>> getBundleRecommendations({
    required String listId,
  }) async {
    try {
      final bundles = await remoteDataSource.getBundleRecommendations(
        listId: listId,
      );
      return Right(bundles);
    } on NetworkException catch (e) {
      return Left(NetworkFailure(e.message));
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message));
    } catch (e) {
      return Left(UnknownFailure(e.toString()));
    }
  }

  @override
  Future<Either<Failure, List<ProductRecommendation>>> getSeasonalRecommendations() async {
    try {
      final recommendations = await remoteDataSource.getSeasonalRecommendations();
      return Right(recommendations);
    } on NetworkException catch (e) {
      return Left(NetworkFailure(e.message));
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message));
    } catch (e) {
      return Left(UnknownFailure(e.toString()));
    }
  }
}
