import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:equatable/equatable.dart';
import '../../domain/entities/inventory_item.dart';
import '../../domain/entities/shopping_item.dart';
import '../../domain/repositories/inventory_repository.dart';

// ========== Events ==========

abstract class InventoryEvent extends Equatable {
  const InventoryEvent();

  @override
  List<Object?> get props => [];
}

/// 加载库存列表
class InventoryLoadRequested extends InventoryEvent {
  final ItemCategory? category;
  final bool lowStockOnly;

  const InventoryLoadRequested({
    this.category,
    this.lowStockOnly = false,
  });

  @override
  List<Object?> get props => [category, lowStockOnly];
}

/// 加载低库存商品
class LowStockItemsLoadRequested extends InventoryEvent {
  const LowStockItemsLoadRequested();
}

/// 加载补货建议
class ReplenishmentSuggestionsLoadRequested extends InventoryEvent {
  final int advanceDays;

  const ReplenishmentSuggestionsLoadRequested({this.advanceDays = 7});

  @override
  List<Object?> get props => [advanceDays];
}

/// 创建库存商品
class InventoryItemCreateRequested extends InventoryEvent {
  final String productName;
  final ItemCategory? category;
  final double currentQuantity;
  final double minThreshold;
  final String? unit;
  final String? storageLocation;
  final DateTime? expiryDate;

  const InventoryItemCreateRequested({
    required this.productName,
    this.category,
    required this.currentQuantity,
    required this.minThreshold,
    this.unit,
    this.storageLocation,
    this.expiryDate,
  });

  @override
  List<Object?> get props => [
    productName, category, currentQuantity, minThreshold, unit, storageLocation, expiryDate,
  ];
}

/// 更新库存商品
class InventoryItemUpdateRequested extends InventoryEvent {
  final String itemId;
  final String? productName;
  final ItemCategory? category;
  final double? currentQuantity;
  final double? minThreshold;
  final String? unit;
  final String? storageLocation;
  final DateTime? expiryDate;

  const InventoryItemUpdateRequested({
    required this.itemId,
    this.productName,
    this.category,
    this.currentQuantity,
    this.minThreshold,
    this.unit,
    this.storageLocation,
    this.expiryDate,
  });

  @override
  List<Object?> get props => [
    itemId, productName, category, currentQuantity, minThreshold, unit, storageLocation, expiryDate,
  ];
}

/// 调整库存数量
class InventoryQuantityAdjusted extends InventoryEvent {
  final String itemId;
  final double quantityChange;

  const InventoryQuantityAdjusted({
    required this.itemId,
    required this.quantityChange,
  });

  @override
  List<Object?> get props => [itemId, quantityChange];
}

/// 删除库存商品
class InventoryItemDeleteRequested extends InventoryEvent {
  final String itemId;

  const InventoryItemDeleteRequested(this.itemId);

  @override
  List<Object?> get props => [itemId];
}

/// 记录购买
class PurchaseRecorded extends InventoryEvent {
  final String productName;
  final double quantity;
  final String? unit;
  final double? price;
  final String? merchant;

  const PurchaseRecorded({
    required this.productName,
    required this.quantity,
    this.unit,
    this.price,
    this.merchant,
  });

  @override
  List<Object?> get props => [productName, quantity, unit, price, merchant];
}

/// 加载库存摘要
class InventorySummaryLoadRequested extends InventoryEvent {
  const InventorySummaryLoadRequested();
}

/// 更改分类筛选
class InventoryCategoryFilterChanged extends InventoryEvent {
  final ItemCategory? category;

  const InventoryCategoryFilterChanged(this.category);

  @override
  List<Object?> get props => [category];
}

// ========== States ==========

abstract class InventoryState extends Equatable {
  const InventoryState();

  @override
  List<Object?> get props => [];
}

class InventoryInitial extends InventoryState {
  const InventoryInitial();
}

class InventoryLoading extends InventoryState {
  const InventoryLoading();
}

class InventoryLoaded extends InventoryState {
  final List<InventoryItem> inventoryItems;
  final List<InventoryItem> lowStockItems;
  final List<InventoryItem> replenishmentSuggestions;
  final InventorySummary? summary;
  final ItemCategory? selectedCategory;
  final bool showLowStockOnly;

  const InventoryLoaded({
    this.inventoryItems = const [],
    this.lowStockItems = const [],
    this.replenishmentSuggestions = const [],
    this.summary,
    this.selectedCategory,
    this.showLowStockOnly = false,
  });

  /// 获取筛选后的商品
  List<InventoryItem> get filteredItems {
    var items = showLowStockOnly ? lowStockItems : inventoryItems;
    if (selectedCategory != null) {
      items = items.where((item) => item.category == selectedCategory).toList();
    }
    return items;
  }

  /// 按分类分组的商品
  Map<String, List<InventoryItem>> get itemsByCategory {
    final map = <String, List<InventoryItem>>{};
    for (final item in filteredItems) {
      final categoryName = item.categoryName;
      map.putIfAbsent(categoryName, () => []).add(item);
    }
    return map;
  }

  InventoryLoaded copyWith({
    List<InventoryItem>? inventoryItems,
    List<InventoryItem>? lowStockItems,
    List<InventoryItem>? replenishmentSuggestions,
    InventorySummary? summary,
    ItemCategory? selectedCategory,
    bool clearSelectedCategory = false,
    bool? showLowStockOnly,
  }) {
    return InventoryLoaded(
      inventoryItems: inventoryItems ?? this.inventoryItems,
      lowStockItems: lowStockItems ?? this.lowStockItems,
      replenishmentSuggestions: replenishmentSuggestions ?? this.replenishmentSuggestions,
      summary: summary ?? this.summary,
      selectedCategory: clearSelectedCategory ? null : (selectedCategory ?? this.selectedCategory),
      showLowStockOnly: showLowStockOnly ?? this.showLowStockOnly,
    );
  }

  @override
  List<Object?> get props => [
    inventoryItems, lowStockItems, replenishmentSuggestions,
    summary, selectedCategory, showLowStockOnly,
  ];
}

class InventoryError extends InventoryState {
  final String message;

  const InventoryError(this.message);

  @override
  List<Object?> get props => [message];
}

// ========== BLoC ==========

class InventoryBloc extends Bloc<InventoryEvent, InventoryState> {
  final InventoryRepository repository;

  InventoryBloc({required this.repository}) : super(const InventoryInitial()) {
    on<InventoryLoadRequested>(_onLoadRequested);
    on<LowStockItemsLoadRequested>(_onLowStockItemsLoadRequested);
    on<ReplenishmentSuggestionsLoadRequested>(_onReplenishmentSuggestionsLoadRequested);
    on<InventoryItemCreateRequested>(_onItemCreateRequested);
    on<InventoryItemUpdateRequested>(_onItemUpdateRequested);
    on<InventoryQuantityAdjusted>(_onQuantityAdjusted);
    on<InventoryItemDeleteRequested>(_onItemDeleteRequested);
    on<PurchaseRecorded>(_onPurchaseRecorded);
    on<InventorySummaryLoadRequested>(_onSummaryLoadRequested);
    on<InventoryCategoryFilterChanged>(_onCategoryFilterChanged);
  }

  Future<void> _onLoadRequested(
    InventoryLoadRequested event,
    Emitter<InventoryState> emit,
  ) async {
    emit(const InventoryLoading());

    final result = await repository.getInventoryList(
      category: event.category,
      lowStockOnly: event.lowStockOnly,
    );

    result.fold(
      (failure) => emit(InventoryError(failure.message)),
      (items) => emit(InventoryLoaded(
        inventoryItems: items,
        selectedCategory: event.category,
        showLowStockOnly: event.lowStockOnly,
      )),
    );
  }

  Future<void> _onLowStockItemsLoadRequested(
    LowStockItemsLoadRequested event,
    Emitter<InventoryState> emit,
  ) async {
    final result = await repository.getLowStockItems();

    result.fold(
      (failure) {
        final currentState = state;
        if (currentState is InventoryLoaded) {
          emit(currentState.copyWith(lowStockItems: const []));
        }
      },
      (items) {
        final currentState = state;
        if (currentState is InventoryLoaded) {
          emit(currentState.copyWith(lowStockItems: items));
        } else {
          emit(InventoryLoaded(lowStockItems: items));
        }
      },
    );
  }

  Future<void> _onReplenishmentSuggestionsLoadRequested(
    ReplenishmentSuggestionsLoadRequested event,
    Emitter<InventoryState> emit,
  ) async {
    final result = await repository.getReplenishmentSuggestions(
      advanceDays: event.advanceDays,
    );

    result.fold(
      (failure) {
        final currentState = state;
        if (currentState is InventoryLoaded) {
          emit(currentState.copyWith(replenishmentSuggestions: const []));
        }
      },
      (items) {
        final currentState = state;
        if (currentState is InventoryLoaded) {
          emit(currentState.copyWith(replenishmentSuggestions: items));
        } else {
          emit(InventoryLoaded(replenishmentSuggestions: items));
        }
      },
    );
  }

  Future<void> _onItemCreateRequested(
    InventoryItemCreateRequested event,
    Emitter<InventoryState> emit,
  ) async {
    final result = await repository.createInventoryItem(
      productName: event.productName,
      category: event.category,
      currentQuantity: event.currentQuantity,
      minThreshold: event.minThreshold,
      unit: event.unit,
      storageLocation: event.storageLocation,
      expiryDate: event.expiryDate,
    );

    result.fold(
      (failure) => emit(InventoryError(failure.message)),
      (newItem) {
        final currentState = state;
        if (currentState is InventoryLoaded) {
          emit(currentState.copyWith(
            inventoryItems: [...currentState.inventoryItems, newItem],
          ));
        }
      },
    );
  }

  Future<void> _onItemUpdateRequested(
    InventoryItemUpdateRequested event,
    Emitter<InventoryState> emit,
  ) async {
    final result = await repository.updateInventoryItem(
      itemId: event.itemId,
      productName: event.productName,
      category: event.category,
      currentQuantity: event.currentQuantity,
      minThreshold: event.minThreshold,
      unit: event.unit,
      storageLocation: event.storageLocation,
      expiryDate: event.expiryDate,
    );

    result.fold(
      (failure) => emit(InventoryError(failure.message)),
      (updatedItem) {
        final currentState = state;
        if (currentState is InventoryLoaded) {
          final updatedItems = currentState.inventoryItems.map((item) {
            return item.id == updatedItem.id ? updatedItem : item;
          }).toList();
          emit(currentState.copyWith(inventoryItems: updatedItems));
        }
      },
    );
  }

  Future<void> _onQuantityAdjusted(
    InventoryQuantityAdjusted event,
    Emitter<InventoryState> emit,
  ) async {
    final result = await repository.adjustInventoryQuantity(
      itemId: event.itemId,
      quantityChange: event.quantityChange,
    );

    result.fold(
      (failure) => emit(InventoryError(failure.message)),
      (updatedItem) {
        final currentState = state;
        if (currentState is InventoryLoaded) {
          final updatedItems = currentState.inventoryItems.map((item) {
            return item.id == updatedItem.id ? updatedItem : item;
          }).toList();

          // 也更新低库存列表
          final updatedLowStockItems = updatedItem.needsReplenishment
              ? [...currentState.lowStockItems.where((i) => i.id != updatedItem.id), updatedItem]
              : currentState.lowStockItems.where((i) => i.id != updatedItem.id).toList();

          emit(currentState.copyWith(
            inventoryItems: updatedItems,
            lowStockItems: updatedLowStockItems,
          ));
        }
      },
    );
  }

  Future<void> _onItemDeleteRequested(
    InventoryItemDeleteRequested event,
    Emitter<InventoryState> emit,
  ) async {
    final result = await repository.deleteInventoryItem(event.itemId);

    result.fold(
      (failure) => emit(InventoryError(failure.message)),
      (_) {
        final currentState = state;
        if (currentState is InventoryLoaded) {
          emit(currentState.copyWith(
            inventoryItems: currentState.inventoryItems
                .where((item) => item.id != event.itemId)
                .toList(),
            lowStockItems: currentState.lowStockItems
                .where((item) => item.id != event.itemId)
                .toList(),
          ));
        }
      },
    );
  }

  Future<void> _onPurchaseRecorded(
    PurchaseRecorded event,
    Emitter<InventoryState> emit,
  ) async {
    final result = await repository.recordPurchase(
      productName: event.productName,
      quantity: event.quantity,
      unit: event.unit,
      price: event.price,
      merchant: event.merchant,
    );

    result.fold(
      (failure) => emit(InventoryError(failure.message)),
      (updatedItem) {
        final currentState = state;
        if (currentState is InventoryLoaded) {
          // 更新或添加库存商品
          final existingIndex = currentState.inventoryItems
              .indexWhere((item) => item.id == updatedItem.id);

          List<InventoryItem> updatedItems;
          if (existingIndex >= 0) {
            updatedItems = [...currentState.inventoryItems];
            updatedItems[existingIndex] = updatedItem;
          } else {
            updatedItems = [...currentState.inventoryItems, updatedItem];
          }

          emit(currentState.copyWith(inventoryItems: updatedItems));
        }
      },
    );
  }

  Future<void> _onSummaryLoadRequested(
    InventorySummaryLoadRequested event,
    Emitter<InventoryState> emit,
  ) async {
    final result = await repository.getInventorySummary();

    result.fold(
      (failure) {
        // 摘要加载失败不影响主流程
      },
      (summary) {
        final currentState = state;
        if (currentState is InventoryLoaded) {
          emit(currentState.copyWith(summary: summary));
        } else {
          emit(InventoryLoaded(summary: summary));
        }
      },
    );
  }

  Future<void> _onCategoryFilterChanged(
    InventoryCategoryFilterChanged event,
    Emitter<InventoryState> emit,
  ) async {
    final currentState = state;
    if (currentState is InventoryLoaded) {
      emit(currentState.copyWith(
        selectedCategory: event.category,
        clearSelectedCategory: event.category == null,
      ));
    }
  }
}
