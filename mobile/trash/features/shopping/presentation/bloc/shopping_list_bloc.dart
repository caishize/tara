import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:equatable/equatable.dart';
import '../../domain/entities/shopping_list.dart';
import '../../domain/entities/shopping_item.dart';
import '../../domain/entities/product_recommendation.dart';
import '../../domain/entities/bundle_opportunity.dart';
import '../../domain/repositories/shopping_repository.dart';

// ========== Events ==========

abstract class ShoppingListEvent extends Equatable {
  const ShoppingListEvent();

  @override
  List<Object?> get props => [];
}

/// 加载购物清单列表
class ShoppingListsLoadRequested extends ShoppingListEvent {
  final ListStatus? statusFilter;
  final ListType? listTypeFilter;

  const ShoppingListsLoadRequested({
    this.statusFilter,
    this.listTypeFilter,
  });

  @override
  List<Object?> get props => [statusFilter, listTypeFilter];
}

/// 创建购物清单
class ShoppingListCreateRequested extends ShoppingListEvent {
  final String listName;
  final ListType listType;
  final DateTime? dueDate;

  const ShoppingListCreateRequested({
    required this.listName,
    required this.listType,
    this.dueDate,
  });

  @override
  List<Object?> get props => [listName, listType, dueDate];
}

/// 选择购物清单（加载详情）
class ShoppingListSelected extends ShoppingListEvent {
  final String listId;

  const ShoppingListSelected(this.listId);

  @override
  List<Object?> get props => [listId];
}

/// 更新购物清单
class ShoppingListUpdateRequested extends ShoppingListEvent {
  final String listId;
  final String? listName;
  final ListType? listType;
  final ListStatus? status;
  final DateTime? dueDate;

  const ShoppingListUpdateRequested({
    required this.listId,
    this.listName,
    this.listType,
    this.status,
    this.dueDate,
  });

  @override
  List<Object?> get props => [listId, listName, listType, status, dueDate];
}

/// 完成购物清单
class ShoppingListCompleted extends ShoppingListEvent {
  final String listId;

  const ShoppingListCompleted(this.listId);

  @override
  List<Object?> get props => [listId];
}

/// 删除购物清单
class ShoppingListDeleted extends ShoppingListEvent {
  final String listId;

  const ShoppingListDeleted(this.listId);

  @override
  List<Object?> get props => [listId];
}

/// 加载清单商品
class ShoppingItemsLoadRequested extends ShoppingListEvent {
  final String listId;
  final String? category;
  final bool? purchased;

  const ShoppingItemsLoadRequested({
    required this.listId,
    this.category,
    this.purchased,
  });

  @override
  List<Object?> get props => [listId, category, purchased];
}

/// 添加商品
class ShoppingItemAddRequested extends ShoppingListEvent {
  final String listId;
  final String productName;
  final String? category;
  final double quantity;
  final String? unit;
  final int priority;
  final double? estimatedPrice;
  final String? notes;

  const ShoppingItemAddRequested({
    required this.listId,
    required this.productName,
    this.category,
    this.quantity = 1,
    this.unit,
    this.priority = 3,
    this.estimatedPrice,
    this.notes,
  });

  @override
  List<Object?> get props => [
    listId, productName, category, quantity, unit, priority, estimatedPrice, notes,
  ];
}

/// 通过AI添加商品
class ShoppingItemAddFromAIRequested extends ShoppingListEvent {
  final String listId;
  final String conversationText;

  const ShoppingItemAddFromAIRequested({
    required this.listId,
    required this.conversationText,
  });

  @override
  List<Object?> get props => [listId, conversationText];
}

/// 更新商品
class ShoppingItemUpdateRequested extends ShoppingListEvent {
  final String listId;
  final String itemId;
  final String? productName;
  final String? category;
  final double? quantity;
  final String? unit;
  final int? priority;
  final double? estimatedPrice;
  final String? notes;

  const ShoppingItemUpdateRequested({
    required this.listId,
    required this.itemId,
    this.productName,
    this.category,
    this.quantity,
    this.unit,
    this.priority,
    this.estimatedPrice,
    this.notes,
  });

  @override
  List<Object?> get props => [
    listId, itemId, productName, category, quantity, unit, priority, estimatedPrice, notes,
  ];
}

/// 标记商品已购买
class ShoppingItemPurchased extends ShoppingListEvent {
  final String listId;
  final String itemId;
  final double? actualPrice;
  final String? merchant;

  const ShoppingItemPurchased({
    required this.listId,
    required this.itemId,
    this.actualPrice,
    this.merchant,
  });

  @override
  List<Object?> get props => [listId, itemId, actualPrice, merchant];
}

/// 删除商品
class ShoppingItemDeleted extends ShoppingListEvent {
  final String listId;
  final String itemId;

  const ShoppingItemDeleted({
    required this.listId,
    required this.itemId,
  });

  @override
  List<Object?> get props => [listId, itemId];
}

/// 更新商品状态（新增）
class ShoppingItemStatusUpdateRequested extends ShoppingListEvent {
  final String listId;
  final String itemId;
  final ItemStatus itemStatus;
  final String? trackingNumber;
  final DateTime? expectedDeliveryDate;

  const ShoppingItemStatusUpdateRequested({
    required this.listId,
    required this.itemId,
    required this.itemStatus,
    this.trackingNumber,
    this.expectedDeliveryDate,
  });

  @override
  List<Object?> get props => [listId, itemId, itemStatus, trackingNumber, expectedDeliveryDate];
}

/// 取消商品订单（新增）
class ShoppingItemCancelOrderRequested extends ShoppingListEvent {
  final String listId;
  final String itemId;

  const ShoppingItemCancelOrderRequested({
    required this.listId,
    required this.itemId,
  });

  @override
  List<Object?> get props => [listId, itemId];
}

/// 更改分类筛选
class CategoryFilterChanged extends ShoppingListEvent {
  final String? category;

  const CategoryFilterChanged(this.category);

  @override
  List<Object?> get props => [category];
}

/// 更改状态筛选
class StatusFilterChanged extends ShoppingListEvent {
  final ListStatus? status;

  const StatusFilterChanged(this.status);

  @override
  List<Object?> get props => [status];
}

/// 加载推荐商品
class ProductRecommendationsLoadRequested extends ShoppingListEvent {
  final int limit;

  const ProductRecommendationsLoadRequested({this.limit = 10});

  @override
  List<Object?> get props => [limit];
}

/// 加载凑单建议
class BundleOpportunitiesLoadRequested extends ShoppingListEvent {
  final String listId;

  const BundleOpportunitiesLoadRequested(this.listId);

  @override
  List<Object?> get props => [listId];
}

/// 加载季节性推荐
class SeasonalRecommendationsLoadRequested extends ShoppingListEvent {
  const SeasonalRecommendationsLoadRequested();
}

// ========== States ==========

abstract class ShoppingListState extends Equatable {
  const ShoppingListState();

  @override
  List<Object?> get props => [];
}

class ShoppingListInitial extends ShoppingListState {
  const ShoppingListInitial();
}

class ShoppingListLoading extends ShoppingListState {
  const ShoppingListLoading();
}

class ShoppingListLoaded extends ShoppingListState {
  final List<ShoppingList> lists;
  final ShoppingList? selectedList;
  final List<ShoppingItem> items;
  final String? selectedCategory;
  final ListStatus? selectedStatus;
  final bool isLoadingItems;
  final List<ProductRecommendation> productRecommendations;
  final List<BundleOpportunity> bundleOpportunities;
  final List<ProductRecommendation> seasonalRecommendations;

  const ShoppingListLoaded({
    this.lists = const [],
    this.selectedList,
    this.items = const [],
    this.selectedCategory,
    this.selectedStatus,
    this.isLoadingItems = false,
    this.productRecommendations = const [],
    this.bundleOpportunities = const [],
    this.seasonalRecommendations = const [],
  });

  /// 获取筛选后的商品
  List<ShoppingItem> get filteredItems {
    return items.where((item) {
      if (selectedCategory != null && item.categoryName != selectedCategory) {
        return false;
      }
      return true;
    }).toList();
  }

  /// 获取未购买的商品
  List<ShoppingItem> get unpurchasedItems => items.where((i) => !i.isPurchased).toList();

  /// 获取已购买的商品
  List<ShoppingItem> get purchasedItems => items.where((i) => i.isPurchased).toList();

  /// 计算总预估价格
  double get totalEstimatedPrice {
    return items.fold(0.0, (sum, item) => sum + (item.estimatedPrice ?? 0) * item.quantity);
  }

  /// 计算总实际价格
  double get totalActualPrice {
    return purchasedItems.fold(0.0, (sum, item) => sum + (item.actualPrice ?? item.estimatedPrice ?? 0) * item.quantity);
  }

  ShoppingListLoaded copyWith({
    List<ShoppingList>? lists,
    ShoppingList? selectedList,
    bool clearSelectedList = false,
    List<ShoppingItem>? items,
    String? selectedCategory,
    bool clearSelectedCategory = false,
    ListStatus? selectedStatus,
    bool clearSelectedStatus = false,
    bool? isLoadingItems,
    List<ProductRecommendation>? productRecommendations,
    List<BundleOpportunity>? bundleOpportunities,
    List<ProductRecommendation>? seasonalRecommendations,
  }) {
    return ShoppingListLoaded(
      lists: lists ?? this.lists,
      selectedList: clearSelectedList ? null : (selectedList ?? this.selectedList),
      items: items ?? this.items,
      selectedCategory: clearSelectedCategory ? null : (selectedCategory ?? this.selectedCategory),
      selectedStatus: clearSelectedStatus ? null : (selectedStatus ?? this.selectedStatus),
      isLoadingItems: isLoadingItems ?? this.isLoadingItems,
      productRecommendations: productRecommendations ?? this.productRecommendations,
      bundleOpportunities: bundleOpportunities ?? this.bundleOpportunities,
      seasonalRecommendations: seasonalRecommendations ?? this.seasonalRecommendations,
    );
  }

  @override
  List<Object?> get props => [
    lists, selectedList, items, selectedCategory, selectedStatus, isLoadingItems,
    productRecommendations, bundleOpportunities, seasonalRecommendations,
  ];
}

class ShoppingListError extends ShoppingListState {
  final String message;

  const ShoppingListError(this.message);

  @override
  List<Object?> get props => [message];
}

class ShoppingListOperationSuccess extends ShoppingListState {
  final String message;

  const ShoppingListOperationSuccess(this.message);

  @override
  List<Object?> get props => [message];
}

/// 购物清单删除成功状态
class ShoppingListDeleteSuccess extends ShoppingListState {
  final String listId;
  final String listName;

  const ShoppingListDeleteSuccess({
    required this.listId,
    required this.listName,
  });

  @override
  List<Object?> get props => [listId, listName];
}

// ========== BLoC ==========

class ShoppingListBloc extends Bloc<ShoppingListEvent, ShoppingListState> {
  final ShoppingRepository repository;

  ShoppingListBloc({required this.repository}) : super(const ShoppingListInitial()) {
    on<ShoppingListsLoadRequested>(_onListsLoadRequested);
    on<ShoppingListCreateRequested>(_onListCreateRequested);
    on<ShoppingListSelected>(_onListSelected);
    on<ShoppingListUpdateRequested>(_onListUpdateRequested);
    on<ShoppingListCompleted>(_onListCompleted);
    on<ShoppingListDeleted>(_onListDeleted);
    on<ShoppingItemsLoadRequested>(_onItemsLoadRequested);
    on<ShoppingItemAddRequested>(_onItemAddRequested);
    on<ShoppingItemAddFromAIRequested>(_onItemAddFromAIRequested);
    on<ShoppingItemUpdateRequested>(_onItemUpdateRequested);
    on<ShoppingItemPurchased>(_onItemPurchased);
    on<ShoppingItemDeleted>(_onItemDeleted);
    on<ShoppingItemStatusUpdateRequested>(_onItemStatusUpdateRequested);
    on<ShoppingItemCancelOrderRequested>(_onItemCancelOrderRequested);
    on<CategoryFilterChanged>(_onCategoryFilterChanged);
    on<StatusFilterChanged>(_onStatusFilterChanged);
    on<ProductRecommendationsLoadRequested>(_onProductRecommendationsLoadRequested);
    on<BundleOpportunitiesLoadRequested>(_onBundleOpportunitiesLoadRequested);
    on<SeasonalRecommendationsLoadRequested>(_onSeasonalRecommendationsLoadRequested);
  }

  Future<void> _onListsLoadRequested(
    ShoppingListsLoadRequested event,
    Emitter<ShoppingListState> emit,
  ) async {
    emit(const ShoppingListLoading());

    final result = await repository.getShoppingLists(
      statusFilter: event.statusFilter,
      listTypeFilter: event.listTypeFilter,
    );

    result.fold(
      (failure) => emit(ShoppingListError(failure.message)),
      (lists) => emit(ShoppingListLoaded(
        lists: lists,
        selectedStatus: event.statusFilter,
      )),
    );
  }

  Future<void> _onListCreateRequested(
    ShoppingListCreateRequested event,
    Emitter<ShoppingListState> emit,
  ) async {
    final currentState = state;
    emit(const ShoppingListLoading());

    final result = await repository.createShoppingList(
      listName: event.listName,
      listType: event.listType,
      dueDate: event.dueDate,
    );

    await result.fold(
      (failure) async => emit(ShoppingListError(failure.message)),
      (newList) async {
        // 重新加载列表
        final listsResult = await repository.getShoppingLists();
        listsResult.fold(
          (failure) => emit(ShoppingListError(failure.message)),
          (lists) {
            if (currentState is ShoppingListLoaded) {
              emit(currentState.copyWith(lists: lists, selectedList: newList));
            } else {
              emit(ShoppingListLoaded(lists: lists, selectedList: newList));
            }
          },
        );
      },
    );
  }

  Future<void> _onListSelected(
    ShoppingListSelected event,
    Emitter<ShoppingListState> emit,
  ) async {
    final currentState = state;
    if (currentState is ShoppingListLoaded) {
      emit(currentState.copyWith(isLoadingItems: true));
    }

    final listResult = await repository.getShoppingListById(event.listId);
    final itemsResult = await repository.getListItems(listId: event.listId);

    listResult.fold(
      (failure) => emit(ShoppingListError(failure.message)),
      (list) {
        itemsResult.fold(
          (failure) => emit(ShoppingListError(failure.message)),
          (items) {
            if (currentState is ShoppingListLoaded) {
              emit(currentState.copyWith(
                selectedList: list,
                items: items,
                isLoadingItems: false,
              ));
            } else {
              emit(ShoppingListLoaded(
                selectedList: list,
                items: items,
              ));
            }
          },
        );
      },
    );
  }

  Future<void> _onListUpdateRequested(
    ShoppingListUpdateRequested event,
    Emitter<ShoppingListState> emit,
  ) async {
    final currentState = state;
    final result = await repository.updateShoppingList(
      listId: event.listId,
      listName: event.listName,
      listType: event.listType,
      status: event.status,
      dueDate: event.dueDate,
    );

    await result.fold(
      (failure) async => emit(ShoppingListError(failure.message)),
      (updatedList) async {
        // Reload the full list to ensure consistency across all pages
        final listsResult = await repository.getShoppingLists();
        listsResult.fold(
          (failure) {
            // If reload fails, at least update the local state
            if (currentState is ShoppingListLoaded) {
              final updatedLists = currentState.lists.map((list) {
                return list.id == updatedList.id ? updatedList : list;
              }).toList();
              emit(currentState.copyWith(
                lists: updatedLists,
                selectedList: currentState.selectedList?.id == updatedList.id
                    ? updatedList
                    : currentState.selectedList,
              ));
            }
          },
          (lists) {
            if (currentState is ShoppingListLoaded) {
              emit(currentState.copyWith(
                lists: lists,
                selectedList: updatedList,
              ));
            } else {
              emit(ShoppingListLoaded(
                lists: lists,
                selectedList: updatedList,
              ));
            }
          },
        );
      },
    );
  }

  Future<void> _onListCompleted(
    ShoppingListCompleted event,
    Emitter<ShoppingListState> emit,
  ) async {
    final currentState = state;
    final result = await repository.completeShoppingList(event.listId);

    await result.fold(
      (failure) async => emit(ShoppingListError(failure.message)),
      (completedList) async {
        // Reload the full list to ensure consistency across all pages
        final listsResult = await repository.getShoppingLists();
        listsResult.fold(
          (failure) {
            // If reload fails, at least update the local state
            if (currentState is ShoppingListLoaded) {
              final updatedLists = currentState.lists.map((list) {
                return list.id == completedList.id ? completedList : list;
              }).toList();
              emit(currentState.copyWith(
                lists: updatedLists,
                selectedList: currentState.selectedList?.id == completedList.id
                    ? completedList
                    : currentState.selectedList,
              ));
            }
          },
          (lists) {
            if (currentState is ShoppingListLoaded) {
              emit(currentState.copyWith(
                lists: lists,
                selectedList: completedList,
              ));
            } else {
              emit(ShoppingListLoaded(
                lists: lists,
                selectedList: completedList,
              ));
            }
          },
        );
      },
    );
  }

  Future<void> _onListDeleted(
    ShoppingListDeleted event,
    Emitter<ShoppingListState> emit,
  ) async {
    final currentState = state;
    // Get the list name before deletion for the success message
    String? listName;
    if (currentState is ShoppingListLoaded) {
      final list = currentState.lists.where((l) => l.id == event.listId).firstOrNull;
      listName = list?.listName ?? '购物清单';
    }

    final result = await repository.deleteShoppingList(event.listId);

    result.fold(
      (failure) => emit(ShoppingListError(failure.message)),
      (_) {
        if (currentState is ShoppingListLoaded) {
          final updatedLists = currentState.lists
              .where((list) => list.id != event.listId)
              .toList();
          // Emit delete success first so listeners can react (e.g., show snackbar)
          emit(ShoppingListDeleteSuccess(
            listId: event.listId,
            listName: listName ?? '购物清单',
          ));
          // Then emit updated list
          emit(currentState.copyWith(
            lists: updatedLists,
            clearSelectedList: currentState.selectedList?.id == event.listId,
          ));
        }
      },
    );
  }

  Future<void> _onItemsLoadRequested(
    ShoppingItemsLoadRequested event,
    Emitter<ShoppingListState> emit,
  ) async {
    final currentState = state;
    if (currentState is ShoppingListLoaded) {
      emit(currentState.copyWith(isLoadingItems: true));
    }

    final result = await repository.getListItems(
      listId: event.listId,
      category: event.category,
      purchased: event.purchased,
    );

    result.fold(
      (failure) => emit(ShoppingListError(failure.message)),
      (items) {
        if (currentState is ShoppingListLoaded) {
          emit(currentState.copyWith(items: items, isLoadingItems: false));
        } else {
          emit(ShoppingListLoaded(items: items));
        }
      },
    );
  }

  Future<void> _onItemAddRequested(
    ShoppingItemAddRequested event,
    Emitter<ShoppingListState> emit,
  ) async {
    final result = await repository.addItem(
      listId: event.listId,
      productName: event.productName,
      category: event.category,
      quantity: event.quantity,
      unit: event.unit,
      priority: event.priority,
      estimatedPrice: event.estimatedPrice,
      notes: event.notes,
    );

    result.fold(
      (failure) => emit(ShoppingListError(failure.message)),
      (newItem) {
        final currentState = state;
        if (currentState is ShoppingListLoaded) {
          emit(currentState.copyWith(
            items: [...currentState.items, newItem],
          ));
        }
      },
    );
  }

  Future<void> _onItemAddFromAIRequested(
    ShoppingItemAddFromAIRequested event,
    Emitter<ShoppingListState> emit,
  ) async {
    final result = await repository.addItemFromConversation(
      listId: event.listId,
      conversationText: event.conversationText,
    );

    result.fold(
      (failure) => emit(ShoppingListError(failure.message)),
      (newItem) {
        final currentState = state;
        if (currentState is ShoppingListLoaded) {
          emit(currentState.copyWith(
            items: [...currentState.items, newItem],
          ));
        }
      },
    );
  }

  Future<void> _onItemUpdateRequested(
    ShoppingItemUpdateRequested event,
    Emitter<ShoppingListState> emit,
  ) async {
    final result = await repository.updateItem(
      listId: event.listId,
      itemId: event.itemId,
      productName: event.productName,
      category: event.category,
      quantity: event.quantity,
      unit: event.unit,
      priority: event.priority,
      estimatedPrice: event.estimatedPrice,
      notes: event.notes,
    );

    result.fold(
      (failure) => emit(ShoppingListError(failure.message)),
      (updatedItem) {
        final currentState = state;
        if (currentState is ShoppingListLoaded) {
          final updatedItems = currentState.items.map((item) {
            return item.id == updatedItem.id ? updatedItem : item;
          }).toList();
          emit(currentState.copyWith(items: updatedItems));
        }
      },
    );
  }

  Future<void> _onItemPurchased(
    ShoppingItemPurchased event,
    Emitter<ShoppingListState> emit,
  ) async {
    final result = await repository.markItemPurchased(
      listId: event.listId,
      itemId: event.itemId,
      actualPrice: event.actualPrice,
      merchant: event.merchant,
    );

    await result.fold(
      (failure) async => emit(ShoppingListError(failure.message)),
      (updatedItem) async {
        final currentState = state;
        if (currentState is ShoppingListLoaded) {
          final updatedItems = currentState.items.map((item) {
            return item.id == updatedItem.id ? updatedItem : item;
          }).toList();

          // 同时更新清单统计信息
          final listResult = await repository.getShoppingListById(event.listId);
          listResult.fold(
            (failure) => emit(currentState.copyWith(items: updatedItems)),
            (updatedList) {
              final updatedLists = currentState.lists.map((list) {
                return list.id == updatedList.id ? updatedList : list;
              }).toList();
              emit(currentState.copyWith(
                items: updatedItems,
                lists: updatedLists,
                selectedList: currentState.selectedList?.id == updatedList.id
                    ? updatedList
                    : currentState.selectedList,
              ));
            },
          );
        }
      },
    );
  }

  Future<void> _onItemDeleted(
    ShoppingItemDeleted event,
    Emitter<ShoppingListState> emit,
  ) async {
    final result = await repository.deleteItem(
      listId: event.listId,
      itemId: event.itemId,
    );

    result.fold(
      (failure) => emit(ShoppingListError(failure.message)),
      (_) {
        final currentState = state;
        if (currentState is ShoppingListLoaded) {
          final updatedItems = currentState.items
              .where((item) => item.id != event.itemId)
              .toList();
          emit(currentState.copyWith(items: updatedItems));
        }
      },
    );
  }

  Future<void> _onItemStatusUpdateRequested(
    ShoppingItemStatusUpdateRequested event,
    Emitter<ShoppingListState> emit,
  ) async {
    final result = await repository.updateItemStatus(
      listId: event.listId,
      itemId: event.itemId,
      itemStatus: event.itemStatus,
      trackingNumber: event.trackingNumber,
      expectedDeliveryDate: event.expectedDeliveryDate,
    );

    await result.fold(
      (failure) async => emit(ShoppingListError(failure.message)),
      (updatedItem) async {
        final currentState = state;
        if (currentState is ShoppingListLoaded) {
          final updatedItems = currentState.items.map((item) {
            return item.id == updatedItem.id ? updatedItem : item;
          }).toList();

          // 同时更新清单统计信息
          final listResult = await repository.getShoppingListById(event.listId);
          listResult.fold(
            (failure) => emit(currentState.copyWith(items: updatedItems)),
            (updatedList) {
              final updatedLists = currentState.lists.map((list) {
                return list.id == updatedList.id ? updatedList : list;
              }).toList();
              emit(currentState.copyWith(
                items: updatedItems,
                lists: updatedLists,
                selectedList: currentState.selectedList?.id == updatedList.id
                    ? updatedList
                    : currentState.selectedList,
              ));
            },
          );
        }
      },
    );
  }

  Future<void> _onItemCancelOrderRequested(
    ShoppingItemCancelOrderRequested event,
    Emitter<ShoppingListState> emit,
  ) async {
    final result = await repository.cancelItemOrder(
      listId: event.listId,
      itemId: event.itemId,
    );

    await result.fold(
      (failure) async => emit(ShoppingListError(failure.message)),
      (updatedItem) async {
        final currentState = state;
        if (currentState is ShoppingListLoaded) {
          final updatedItems = currentState.items.map((item) {
            return item.id == updatedItem.id ? updatedItem : item;
          }).toList();

          // 同时更新清单统计信息
          final listResult = await repository.getShoppingListById(event.listId);
          listResult.fold(
            (failure) => emit(currentState.copyWith(items: updatedItems)),
            (updatedList) {
              final updatedLists = currentState.lists.map((list) {
                return list.id == updatedList.id ? updatedList : list;
              }).toList();
              emit(currentState.copyWith(
                items: updatedItems,
                lists: updatedLists,
                selectedList: currentState.selectedList?.id == updatedList.id
                    ? updatedList
                    : currentState.selectedList,
              ));
            },
          );
        }
      },
    );
  }

  Future<void> _onCategoryFilterChanged(
    CategoryFilterChanged event,
    Emitter<ShoppingListState> emit,
  ) async {
    final currentState = state;
    if (currentState is ShoppingListLoaded) {
      emit(currentState.copyWith(
        selectedCategory: event.category,
        clearSelectedCategory: event.category == null,
      ));
    }
  }

  Future<void> _onStatusFilterChanged(
    StatusFilterChanged event,
    Emitter<ShoppingListState> emit,
  ) async {
    final currentState = state;
    if (currentState is ShoppingListLoaded) {
      emit(currentState.copyWith(
        selectedStatus: event.status,
        clearSelectedStatus: event.status == null,
      ));
    }
  }

  Future<void> _onProductRecommendationsLoadRequested(
    ProductRecommendationsLoadRequested event,
    Emitter<ShoppingListState> emit,
  ) async {
    final result = await repository.getProductRecommendations(limit: event.limit);

    result.fold(
      (failure) {
        // 推荐加载失败不影响主流程
        final currentState = state;
        if (currentState is ShoppingListLoaded) {
          emit(currentState.copyWith(productRecommendations: const []));
        }
      },
      (recommendations) {
        final currentState = state;
        if (currentState is ShoppingListLoaded) {
          emit(currentState.copyWith(productRecommendations: recommendations));
        } else {
          emit(ShoppingListLoaded(productRecommendations: recommendations));
        }
      },
    );
  }

  Future<void> _onBundleOpportunitiesLoadRequested(
    BundleOpportunitiesLoadRequested event,
    Emitter<ShoppingListState> emit,
  ) async {
    final result = await repository.getBundleRecommendations(listId: event.listId);

    result.fold(
      (failure) {
        // 凑单加载失败不影响主流程
        final currentState = state;
        if (currentState is ShoppingListLoaded) {
          emit(currentState.copyWith(bundleOpportunities: const []));
        }
      },
      (opportunities) {
        final currentState = state;
        if (currentState is ShoppingListLoaded) {
          emit(currentState.copyWith(bundleOpportunities: opportunities));
        } else {
          emit(ShoppingListLoaded(bundleOpportunities: opportunities));
        }
      },
    );
  }

  Future<void> _onSeasonalRecommendationsLoadRequested(
    SeasonalRecommendationsLoadRequested event,
    Emitter<ShoppingListState> emit,
  ) async {
    final result = await repository.getSeasonalRecommendations();

    result.fold(
      (failure) {
        // 季节推荐加载失败不影响主流程
        final currentState = state;
        if (currentState is ShoppingListLoaded) {
          emit(currentState.copyWith(seasonalRecommendations: const []));
        }
      },
      (recommendations) {
        final currentState = state;
        if (currentState is ShoppingListLoaded) {
          emit(currentState.copyWith(seasonalRecommendations: recommendations));
        } else {
          emit(ShoppingListLoaded(seasonalRecommendations: recommendations));
        }
      },
    );
  }
}
