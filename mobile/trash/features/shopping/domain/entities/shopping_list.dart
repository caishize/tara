import 'package:equatable/equatable.dart';

/// 购物清单类型
enum ListType {
  regular,      // 日常购物
  replenishment, // 补货
  seasonal,     // 季节性采购
  bulk,         // 批量采购
  urgent,       // 紧急购物
}

/// 购物清单状态
enum ListStatus {
  active,       // 活跃
  inProgress,   // 进行中
  completed,    // 已完成
  archived,     // 已归档
}

/// 购物清单实体
class ShoppingList extends Equatable {
  final String id;
  final String familyId;
  final String createdBy;
  final String listName;
  final ListType listType;
  final ListStatus status;
  final DateTime? dueDate;
  final int totalItems;
  final int purchasedItems;
  final double completionPercentage;
  final DateTime createdAt;
  final DateTime updatedAt;
  final DateTime? completedAt;

  const ShoppingList({
    required this.id,
    required this.familyId,
    required this.createdBy,
    required this.listName,
    required this.listType,
    required this.status,
    this.dueDate,
    this.totalItems = 0,
    this.purchasedItems = 0,
    this.completionPercentage = 0.0,
    required this.createdAt,
    required this.updatedAt,
    this.completedAt,
  });

  /// 是否已过期
  bool get isOverdue {
    if (dueDate == null) return false;
    return DateTime.now().isAfter(dueDate!) && status != ListStatus.completed;
  }

  /// 剩余天数
  int? get daysUntilDue {
    if (dueDate == null) return null;
    return dueDate!.difference(DateTime.now()).inDays;
  }

  /// 获取类型显示名称
  String get listTypeName {
    switch (listType) {
      case ListType.regular:
        return '日常购物';
      case ListType.replenishment:
        return '补货';
      case ListType.seasonal:
        return '季节采购';
      case ListType.bulk:
        return '批量采购';
      case ListType.urgent:
        return '紧急购物';
    }
  }

  /// 获取类型图标
  String get listTypeIcon {
    switch (listType) {
      case ListType.regular:
        return '🛒';
      case ListType.replenishment:
        return '🔄';
      case ListType.seasonal:
        return '🌸';
      case ListType.bulk:
        return '📦';
      case ListType.urgent:
        return '⚡';
    }
  }

  /// 获取状态显示名称
  String get statusName {
    switch (status) {
      case ListStatus.active:
        return '待购';
      case ListStatus.inProgress:
        return '购物中';
      case ListStatus.completed:
        return '已完成';
      case ListStatus.archived:
        return '已归档';
    }
  }

  /// Alias for completionPercentage (0.0 to 1.0 range)
  double get completionRate => completionPercentage / 100.0;

  /// Alias for totalItems
  int get totalItemCount => totalItems;

  /// Alias for purchasedItems
  int get purchasedItemCount => purchasedItems;

  /// Estimated total price (placeholder - will be calculated from items)
  double get estimatedTotal => 0.0;

  ShoppingList copyWith({
    String? id,
    String? familyId,
    String? createdBy,
    String? listName,
    ListType? listType,
    ListStatus? status,
    DateTime? dueDate,
    int? totalItems,
    int? purchasedItems,
    double? completionPercentage,
    DateTime? createdAt,
    DateTime? updatedAt,
    DateTime? completedAt,
  }) {
    return ShoppingList(
      id: id ?? this.id,
      familyId: familyId ?? this.familyId,
      createdBy: createdBy ?? this.createdBy,
      listName: listName ?? this.listName,
      listType: listType ?? this.listType,
      status: status ?? this.status,
      dueDate: dueDate ?? this.dueDate,
      totalItems: totalItems ?? this.totalItems,
      purchasedItems: purchasedItems ?? this.purchasedItems,
      completionPercentage: completionPercentage ?? this.completionPercentage,
      createdAt: createdAt ?? this.createdAt,
      updatedAt: updatedAt ?? this.updatedAt,
      completedAt: completedAt ?? this.completedAt,
    );
  }

  @override
  List<Object?> get props => [
    id, familyId, createdBy, listName, listType, status, dueDate,
    totalItems, purchasedItems, completionPercentage, createdAt, updatedAt, completedAt,
  ];
}
