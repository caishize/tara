import 'package:equatable/equatable.dart';

/// 支出类别
enum ExpenseCategory {
  transportation,  // 交通
  accommodation,   // 住宿
  tickets,         // 门票
  food,            // 餐饮
  shopping,        // 购物
  other,           // 其他
}

/// 旅行支出实体
class TripExpense extends Equatable {
  final String id;
  final String tripId;
  final ExpenseCategory category;
  final double amount;
  final DateTime expenseDate;
  final String? description;
  final String? location;
  final String? paymentMethod;
  final String? receiptUrl;
  final String? itineraryItemId;
  final DateTime createdAt;
  final DateTime updatedAt;

  const TripExpense({
    required this.id,
    required this.tripId,
    required this.category,
    required this.amount,
    required this.expenseDate,
    this.description,
    this.location,
    this.paymentMethod,
    this.receiptUrl,
    this.itineraryItemId,
    required this.createdAt,
    required this.updatedAt,
  });

  /// 类别显示名称
  String get categoryName {
    switch (category) {
      case ExpenseCategory.transportation:
        return '交通';
      case ExpenseCategory.accommodation:
        return '住宿';
      case ExpenseCategory.tickets:
        return '门票';
      case ExpenseCategory.food:
        return '餐饮';
      case ExpenseCategory.shopping:
        return '购物';
      case ExpenseCategory.other:
        return '其他';
    }
  }

  /// 类别图标
  String get categoryIcon {
    switch (category) {
      case ExpenseCategory.transportation:
        return '🚗';
      case ExpenseCategory.accommodation:
        return '🏨';
      case ExpenseCategory.tickets:
        return '🎟️';
      case ExpenseCategory.food:
        return '🍽️';
      case ExpenseCategory.shopping:
        return '🛍️';
      case ExpenseCategory.other:
        return '💰';
    }
  }

  /// 类别颜色值
  int get categoryColorValue {
    switch (category) {
      case ExpenseCategory.transportation:
        return 0xFF42A5F5; // Blue
      case ExpenseCategory.accommodation:
        return 0xFF7E57C2; // Purple
      case ExpenseCategory.tickets:
        return 0xFFFF7043; // Orange
      case ExpenseCategory.food:
        return 0xFF66BB6A; // Green
      case ExpenseCategory.shopping:
        return 0xFFEC407A; // Pink
      case ExpenseCategory.other:
        return 0xFF78909C; // Blue Grey
    }
  }

  TripExpense copyWith({
    String? id,
    String? tripId,
    ExpenseCategory? category,
    double? amount,
    DateTime? expenseDate,
    String? description,
    String? location,
    String? paymentMethod,
    String? receiptUrl,
    String? itineraryItemId,
    DateTime? createdAt,
    DateTime? updatedAt,
  }) {
    return TripExpense(
      id: id ?? this.id,
      tripId: tripId ?? this.tripId,
      category: category ?? this.category,
      amount: amount ?? this.amount,
      expenseDate: expenseDate ?? this.expenseDate,
      description: description ?? this.description,
      location: location ?? this.location,
      paymentMethod: paymentMethod ?? this.paymentMethod,
      receiptUrl: receiptUrl ?? this.receiptUrl,
      itineraryItemId: itineraryItemId ?? this.itineraryItemId,
      createdAt: createdAt ?? this.createdAt,
      updatedAt: updatedAt ?? this.updatedAt,
    );
  }

  @override
  List<Object?> get props => [
    id, tripId, category, amount, expenseDate, description,
    location, paymentMethod, receiptUrl, itineraryItemId, createdAt, updatedAt,
  ];
}

/// 预算状态
class BudgetStatus extends Equatable {
  final String tripId;
  final double totalBudget;
  final double totalSpent;
  final Map<ExpenseCategory, double> categoryBreakdown;
  final bool isOverBudget;
  final double remainingBudget;
  final double usagePercentage;

  const BudgetStatus({
    required this.tripId,
    required this.totalBudget,
    required this.totalSpent,
    required this.categoryBreakdown,
    required this.isOverBudget,
    required this.remainingBudget,
    required this.usagePercentage,
  });

  @override
  List<Object?> get props => [
    tripId, totalBudget, totalSpent, categoryBreakdown,
    isOverBudget, remainingBudget, usagePercentage,
  ];
}
