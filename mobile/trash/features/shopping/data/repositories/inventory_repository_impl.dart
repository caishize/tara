import 'package:dartz/dartz.dart';
import '../../../../core/error/exceptions.dart';
import '../../../../core/error/failures.dart';
import '../../domain/entities/inventory_item.dart';
import '../../domain/entities/shopping_item.dart';
import '../../domain/repositories/inventory_repository.dart';
import '../datasources/inventory_remote_datasource.dart';
import '../models/inventory_item_model.dart';

/// 库存仓库实现
class InventoryRepositoryImpl implements InventoryRepository {
  final InventoryRemoteDataSource remoteDataSource;

  InventoryRepositoryImpl({required this.remoteDataSource});

  @override
  Future<Either<Failure, List<InventoryItem>>> getInventoryList({
    ItemCategory? category,
    bool lowStockOnly = false,
    int page = 1,
    int pageSize = 50,
  }) async {
    try {
      final items = await remoteDataSource.getInventoryList(
        category: category != null ? itemCategoryToString(category) : null,
        lowStockOnly: lowStockOnly,
        page: page,
        pageSize: pageSize,
      );
      return Right(items);
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
  Future<Either<Failure, InventoryItem>> getInventoryItemById(String itemId) async {
    try {
      final item = await remoteDataSource.getInventoryItemById(itemId);
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
  Future<Either<Failure, List<InventoryItem>>> getLowStockItems() async {
    try {
      final items = await remoteDataSource.getLowStockItems();
      return Right(items);
    } on NetworkException catch (e) {
      return Left(NetworkFailure(e.message));
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message));
    } catch (e) {
      return Left(UnknownFailure(e.toString()));
    }
  }

  @override
  Future<Either<Failure, List<InventoryItem>>> getReplenishmentSuggestions({
    int advanceDays = 7,
  }) async {
    try {
      final items = await remoteDataSource.getReplenishmentSuggestions(
        advanceDays: advanceDays,
      );
      return Right(items);
    } on NetworkException catch (e) {
      return Left(NetworkFailure(e.message));
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message));
    } catch (e) {
      return Left(UnknownFailure(e.toString()));
    }
  }

  @override
  Future<Either<Failure, InventoryItem>> createInventoryItem({
    required String productName,
    ItemCategory? category,
    required double currentQuantity,
    required double minThreshold,
    String? unit,
    String? storageLocation,
    DateTime? expiryDate,
  }) async {
    try {
      final item = await remoteDataSource.createInventoryItem(
        productName: productName,
        category: category != null ? itemCategoryToString(category) : null,
        currentQuantity: currentQuantity,
        minThreshold: minThreshold,
        unit: unit,
        storageLocation: storageLocation,
        expiryDate: expiryDate,
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
  Future<Either<Failure, InventoryItem>> updateInventoryItem({
    required String itemId,
    String? productName,
    ItemCategory? category,
    double? currentQuantity,
    double? minThreshold,
    String? unit,
    String? storageLocation,
    DateTime? expiryDate,
  }) async {
    try {
      final item = await remoteDataSource.updateInventoryItem(
        itemId: itemId,
        productName: productName,
        category: category != null ? itemCategoryToString(category) : null,
        currentQuantity: currentQuantity,
        minThreshold: minThreshold,
        unit: unit,
        storageLocation: storageLocation,
        expiryDate: expiryDate,
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
  Future<Either<Failure, InventoryItem>> adjustInventoryQuantity({
    required String itemId,
    required double quantityChange,
  }) async {
    try {
      final item = await remoteDataSource.adjustInventoryQuantity(
        itemId: itemId,
        quantityChange: quantityChange,
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
  Future<Either<Failure, void>> deleteInventoryItem(String itemId) async {
    try {
      await remoteDataSource.deleteInventoryItem(itemId);
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
  Future<Either<Failure, InventoryItem>> recordPurchase({
    required String productName,
    required double quantity,
    String? unit,
    double? price,
    String? merchant,
  }) async {
    try {
      final item = await remoteDataSource.recordPurchase(
        productName: productName,
        quantity: quantity,
        unit: unit,
        price: price,
        merchant: merchant,
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
  Future<Either<Failure, InventorySummary>> getInventorySummary() async {
    try {
      final data = await remoteDataSource.getInventorySummary();
      final lowStockItemsData = data['top_low_stock_items'] as List<dynamic>? ?? [];
      final topLowStockItems = lowStockItemsData
          .map((json) => InventoryItemModel.fromJson(json as Map<String, dynamic>))
          .toList();

      return Right(InventorySummary(
        totalItems: data['total_items'] ?? 0,
        lowStockCount: data['low_stock_count'] ?? 0,
        expiringCount: data['expiring_count'] ?? 0,
        expiredCount: data['expired_count'] ?? 0,
        topLowStockItems: topLowStockItems,
      ));
    } on NetworkException catch (e) {
      return Left(NetworkFailure(e.message));
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message));
    } catch (e) {
      return Left(UnknownFailure(e.toString()));
    }
  }
}
